"""
Feature 7 cleanup compliance scanners.

These scanners provide explicit blockers before irreversible cleanup (CP5).
They are intentionally scoped to production-path modules/templates.
"""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse(path: Path) -> ast.AST | None:
    source = _read(path)
    if not source:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


class CleanupComplianceScanner:
    LISTING_SCOPED_FILES = [
        PROJECT_ROOT / "marketplace" / "views.py",
        PROJECT_ROOT / "marketplace" / "forms.py",
        PROJECT_ROOT / "marketplace" / "matching.py",
        PROJECT_ROOT / "marketplace" / "vector_search.py",
        PROJECT_ROOT / "marketplace" / "notifications.py",
    ]

    MESSAGING_SCOPED_FILES = [
        PROJECT_ROOT / "marketplace" / "views.py",
        PROJECT_ROOT / "marketplace" / "context_processors.py",
        PROJECT_ROOT / "marketplace" / "notifications.py",
    ]

    ROLE_ORG_SCOPED_FILES = [
        PROJECT_ROOT / "marketplace" / "views.py",
        PROJECT_ROOT / "marketplace" / "forms.py",
        PROJECT_ROOT / "marketplace" / "context_processors.py",
    ]

    ROLE_ORG_TEMPLATES = [
        PROJECT_ROOT / "templates" / "marketplace" / "discover.html",
        PROJECT_ROOT / "templates" / "marketplace" / "dashboard.html",
        PROJECT_ROOT / "templates" / "includes" / "_navbar.html",
    ]

    WATCHLIST_TEMPLATE = PROJECT_ROOT / "templates" / "marketplace" / "_watchlist_card.html"

    def scan_listing_model_dependencies(self) -> tuple[bool, list[str]]:
        violations: list[str] = []
        blocked_names = {"DemandPost", "SupplyLot"}

        for path in self.LISTING_SCOPED_FILES:
            tree = _parse(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("models"):
                    for alias in node.names:
                        if alias.name in blocked_names:
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} imports legacy model {alias.name}"
                            )
                if isinstance(node, ast.Name) and node.id in blocked_names:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} references legacy model {node.id}"
                    )

        return (len(violations) == 0), violations

    def scan_messaging_watchlist_legacy_fields(self) -> tuple[bool, list[str]]:
        violations: list[str] = []
        blocked_string_values = {
            "buyer",
            "supplier",
            "watchlist_item",
            "watchlist_item__supply_lot",
            "watchlist_item__demand_post",
            "watchlist_item__supply_lot__created_by",
            "watchlist_item__demand_post__created_by",
        }
        blocked_attrs = {"buyer", "supplier", "watchlist_item"}

        for path in self.MESSAGING_SCOPED_FILES:
            tree = _parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in blocked_string_values:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} uses legacy field '{node.value}'"
                        )
                if isinstance(node, ast.Attribute) and node.attr in blocked_attrs:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} uses legacy attribute '{node.attr}'"
                    )

        template_source = _read(self.WATCHLIST_TEMPLATE)
        for pattern in ["item.supply_lot", "item.demand_post"]:
            if pattern in template_source:
                violations.append(
                    f"{self.WATCHLIST_TEMPLATE.relative_to(PROJECT_ROOT)} contains legacy watchlist field pattern '{pattern}'"
                )

        return (len(violations) == 0), violations

    def scan_role_org_dependencies(self) -> tuple[bool, list[str]]:
        violations: list[str] = []
        blocked_names = {"Role", "Organization"}

        for path in self.ROLE_ORG_SCOPED_FILES:
            tree = _parse(path)
            if tree is None:
                continue
            source_lines = _read(path).splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in blocked_names:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} references legacy identity construct '{node.id}'"
                    )
                if isinstance(node, ast.Attribute) and node.attr == "role":
                    if path.name == "forms.py" and "user.role =" in source_lines[node.lineno - 1]:
                        continue
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} references user role attribute"
                    )

        for path in self.ROLE_ORG_TEMPLATES:
            source = _read(path)
            if "user.role" in source:
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)} contains role-based template usage 'user.role'"
                )

        return (len(violations) == 0), violations
