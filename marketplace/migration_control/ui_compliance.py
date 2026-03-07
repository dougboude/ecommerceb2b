"""
UI derolification compliance scanner (Feature 8).

Scans production templates and selected Python modules for residual role-based
language and role attribute references after CP5 cleanup.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TemplateLanguageComplianceScanner:
    TEMPLATE_ROOTS = [
        PROJECT_ROOT / "templates" / "marketplace",
        PROJECT_ROOT / "templates" / "includes",
        PROJECT_ROOT / "templates" / "registration",
    ]
    PYTHON_FILES = [
        PROJECT_ROOT / "marketplace" / "views.py",
        PROJECT_ROOT / "marketplace" / "forms.py",
    ]

    TEMPLATE_PATTERNS = [
        re.compile(r"user\.role"),
        re.compile(r"request\.user\.role"),
        re.compile(r"{%\s*if[^%]*role[^%]*%}"),
        re.compile(r"Register as Buyer", re.IGNORECASE),
        re.compile(r"Register as Supplier", re.IGNORECASE),
        re.compile(r"Buyer Dashboard", re.IGNORECASE),
        re.compile(r"Supplier Dashboard", re.IGNORECASE),
        re.compile(r"Buyer listing", re.IGNORECASE),
        re.compile(r"Supplier listing", re.IGNORECASE),
    ]

    WARNING_PATTERNS = [
        re.compile(r"role", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def scan(self) -> tuple[bool, list[str]]:
        violations: list[str] = []
        self.warnings = []

        for template_path in self._iter_templates():
            violations.extend(self._scan_template(template_path))

        for python_path in self.PYTHON_FILES:
            violations.extend(self._scan_python(python_path))

        return (len(violations) == 0), violations

    def _iter_templates(self):
        for root in self.TEMPLATE_ROOTS:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.html")):
                yield path

    def _scan_template(self, path: Path) -> list[str]:
        violations: list[str] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return violations

        rel_path = path.relative_to(PROJECT_ROOT)
        for line_no, line in enumerate(lines, start=1):
            for pattern in self.TEMPLATE_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel_path}:{line_no} contains '{pattern.pattern}'")
            stripped = line.strip()
            if stripped.startswith("{#") and stripped.endswith("#}"):
                for pattern in self.WARNING_PATTERNS:
                    if pattern.search(stripped):
                        self.warnings.append(f"{rel_path}:{line_no} comment contains '{pattern.pattern}'")

        return violations

    def _scan_python(self, path: Path) -> list[str]:
        violations: list[str] = []
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return violations

        rel_path = path.relative_to(PROJECT_ROOT)

        for line_no, line in enumerate(source.splitlines(), start=1):
            if "user.role" in line or "request.user.role" in line:
                violations.append(f"{rel_path}:{line_no} references role attribute")
            if "Role.BUYER" in line or "Role.SUPPLIER" in line:
                violations.append(f"{rel_path}:{line_no} references role enum branch")

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("models"):
                for alias in node.names:
                    if alias.name == "Role":
                        violations.append(f"{rel_path}:{node.lineno} imports Role from models")

        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                if re.search(r"role", node.value.value, re.IGNORECASE):
                    self.warnings.append(f"{rel_path}:{node.lineno} docstring contains 'role'")

        return violations
