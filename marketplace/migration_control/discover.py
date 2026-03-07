"""
Discover-direction compliance scanner (Feature 6).

Ensures launch-critical discover paths do not rely on role-based direction
inference and that discover template rendering does not branch on user role.
"""


class DiscoverComplianceScanner:
    """
    Scans discover view helpers and discover template for residual role-based
    discover behavior.
    """

    VIEW_PATTERNS = [
        "user.role == Role.BUYER",
        "user.role == Role.SUPPLIER",
        "if user.role ==",
    ]

    TEMPLATE_PATTERNS = [
        "user.role",
    ]

    VIEW_NAMES = [
        "_run_discover_search",
        "_sort_discover_results",
        "_discover_watchlisted_pks",
        "discover_view",
    ]

    def scan(self) -> tuple[bool, list[str]]:
        import inspect
        from pathlib import Path

        import marketplace.views as views_module

        violations = []
        for view_name in self.VIEW_NAMES:
            fn = getattr(views_module, view_name, None)
            if fn is None:
                continue
            try:
                source = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            for pattern in self.VIEW_PATTERNS:
                if pattern in source:
                    violations.append(
                        f"{view_name}: contains discover role-inference pattern '{pattern}'"
                    )

        template_path = Path(__file__).resolve().parents[2] / "templates" / "marketplace" / "discover.html"
        try:
            with template_path.open("r", encoding="utf-8") as fh:
                template_source = fh.read()
        except OSError:
            template_source = ""

        for pattern in self.TEMPLATE_PATTERNS:
            if pattern in template_source:
                violations.append(
                    f"discover template: contains discover role-inference pattern '{pattern}'"
                )

        return (len(violations) == 0), violations
