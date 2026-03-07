# UI Language and Navigation Derolification — Design Document

## Overview

This spec operates exclusively at **CP5** — after `User.role`, `Organization`, `DemandPost`, and `SupplyLot` have been removed from the codebase. The work is additive and convergent: no database migrations are required. Two phases separate safe reversible convergence from final lock-in:

- **Phase 1 (Convergence):** Replace role-based language and conditionals in templates, forms, and views. Implement the compliance scanner. All changes are reversible via git revert.
- **Phase 2 (Verification Lock):** Run compliance scanner, retire stale migration-era tests, confirm full test suite passes, sign off. After Phase 2 completes there is no intention to re-introduce role language.

## Migration State Gate Design

Before any Phase 1 task begins, the executing agent MUST confirm the following artifact chain passes. If any check fails, execution stops with a documented reason:

```
# Gate 1: Confirm CP5
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
from django.core.exceptions import FieldDoesNotExist
s = get_or_create_state()
assert s.checkpoint_order == 5, f'Expected CP5, got {s.checkpoint}'
print('CP5 confirmed')
"

# Gate 2: Confirm User.role removed
manage.py shell -c "
from marketplace.models import User
from django.core.exceptions import FieldDoesNotExist
try:
    User._meta.get_field('role')
    raise AssertionError('User.role still exists — block execution')
except FieldDoesNotExist:
    print('User.role absent — confirmed')
"

# Gate 3: Confirm legacy models gone
manage.py shell -c "
try:
    from marketplace.models import Organization, DemandPost, SupplyLot
    raise AssertionError('Legacy models still importable — block execution')
except ImportError:
    print('Legacy models absent — confirmed')
"

# Gate 4: Confirm cutover-stage parity reports exist and passed (do NOT re-run validate — query existing reports)
manage.py shell -c "
from marketplace.migration_control.parity import ParityReport
cutover_reports = ParityReport.objects.filter(stage='cutover')
assert cutover_reports.exists(), 'No cutover-stage parity reports found — run legacy-schema-cleanup-and-final-cutover first'
failed = cutover_reports.filter(passed=False)
assert not failed.exists(), f'Cutover-stage failures: {list(failed.values_list(\"scope\", flat=True))}'
print(f'Cutover parity OK — {cutover_reports.count()} reports, all passed')
"
```

All four gates must produce clean output before Phase 1 proceeds.

## Architecture

```
Phase 1: Convergence (reversible)
  ┌─────────────────────────────────────────────────────────────────┐
  │  templates/includes/                                            │
  │  └── _navbar.html         role-conditional → role-agnostic     │
  │                                                                 │
  │  templates/registration/                                        │
  │  └── signup.html          "Create Account", no role selector   │
  │                                                                 │
  │  templates/marketplace/                                         │
  │  ├── base.html            title/meta cleanup                   │
  │  ├── dashboard.html       "Dashboard", no role heading         │
  │  ├── profile.html         both listing types, no role label    │
  │  └── [listing forms]      "Supply" / "Demand" labels only      │
  │                                                                 │
  │  marketplace/forms.py                                           │
  │  └── SignupForm           remove role field / save logic       │
  │                                                                 │
  │  marketplace/views.py                                           │
  │  └── [remaining role      remove any surviving role branches   │
  │       display branches]                                         │
  └─────────────────────────────────────────────────────────────────┘

Phase 2: Verification Lock (irreversible intent)
  ┌─────────────────────────────────────────────────────────────────┐
  │  marketplace/migration_control/ui_compliance.py (new)           │
  │  └── TemplateLanguageComplianceScanner                          │
  │       ├── scans templates/marketplace/*.html                    │
  │       ├── scans marketplace/views.py + forms.py                 │
  │       └── returns (passed: bool, violations: list[str])         │
  │                                                                 │
  │  manage.py migration_validate --scope ui                        │
  │  └── ParityValidator.validate_ui_language()                     │
  │                                                                 │
  │  Full test suite + tagged ui_derolification tests               │
  └─────────────────────────────────────────────────────────────────┘
```

## Phase 1: Template and Form Convergence

### `templates/includes/_navbar.html`

**Current state (pre-spec):** Contains `{% if user.role == "buyer" %}` / `{% if user.role == "supplier" %}` blocks that show different navigation items. With `User.role` removed, these evaluate silently to falsy — the nav items they wrapped are invisible to all users. This is the critical silent dead code this spec fixes.

**Target state:**
```html
<!-- No role conditionals. All items visible to authenticated users. -->
<nav>
  <a href="{% url 'marketplace:dashboard' %}">Dashboard</a>
  <a href="{% url 'marketplace:discover' %}">Discover</a>
  <a href="{% url 'marketplace:inbox' %}">Messages {% if unread_thread_count %}{{ unread_thread_count }}{% endif %}</a>
  <a href="{% url 'marketplace:watchlist' %}">Watchlist</a>
  <!-- Your Listings dropdown or grouped links -->
  <a href="{% url 'marketplace:supply_lot_list' %}">Supply</a>
  <a href="{% url 'marketplace:demand_post_list' %}">Demand</a>
  <a href="{% url 'marketplace:profile' %}">Profile</a>
</nav>
```

The "Your Listings" grouping (Supply / Demand sub-items) may be implemented as a nav group, a dropdown, or two adjacent links — the implementation approach is left to the executing agent. The requirement is that both are always visible to authenticated users.

### `templates/registration/signup.html` and `SignupForm`

**Current state:** `SignupForm` may retain a `role` field assignment in its `save()` method from pre-Feature-2 code. With `User.role` removed, this would raise `AttributeError` on save if not cleaned up in Feature 7. This spec ensures the form and template are clean regardless.

**Target state:**
- `SignupForm.Meta.fields` contains no `role` field
- `SignupForm.save()` contains no `user.role = ...` assignment
- Signup template heading: `<h1>Create Account</h1>`
- Submit button label: `Create Account`
- No copy referencing "Register as Buyer" or "Register as Supplier"

### `dashboard.html`

**Current state:** Page heading and `<title>` likely branch on role (e.g., "Buyer Dashboard" / "Supplier Dashboard"). With `User.role` removed, the heading silently renders as empty or falls through to a default.

**Target state:**
- Page `<title>`: `Dashboard — NicheMarket`
- Page `<h1>` or primary heading: `Dashboard`
- No role-conditional section display. The dashboard shows the user's listings activity in a role-agnostic layout.
- Supply listing activity and demand listing activity are both represented without role-gating.

### `templates/marketplace/profile.html` (self-profile only)

**Scope:** Only the self-profile route (`/profile/`) is in scope. This page shows the authenticated user's own profile. Public profile viewing is not implemented.

**Current state:** Profile page likely shows only one listing type based on the user's role.

**Target state layout:**
```
[Display Name]
[Organization Name (if set)]
[Location: Country, Locality]
[Member since: YYYY]
[Profile image: placeholder initial/avatar — full upload deferred]

Supply Listings
  [list of active supply listings or "No supply listings yet."]

Demand Listings
  [list of active demand listings or "No demand listings yet."]
```

**View changes:**
- Profile view queries `Listing.objects.filter(created_by_user=request.user, type=ListingType.SUPPLY, status=ListingStatus.ACTIVE)` for supply section
- Profile view queries `Listing.objects.filter(created_by_user=request.user, type=ListingType.DEMAND, status=ListingStatus.ACTIVE)` for demand section
- No `user.role` read in the profile view

### Listing Form and Create-Page Labels

**Current state:** Forms and heading copy may use "Supplier listing" / "Wanted listing" language tied to role.

**Target state:**
- Supply create form heading: `New Supply Listing`
- Demand create form heading: `New Demand Listing`
- Supply edit form heading: `Edit Supply Listing`
- Demand edit form heading: `Edit Demand Listing`
- All `<title>` tags for listing forms follow the same naming convention

### Remaining Role Branches in `views.py`

After Feature 7, `views.py` should have no `user.role` checks in production code paths. This spec performs a final audit. Any surviving `user.role` display branches (e.g., in dashboard context building, discover direction defaulting) are removed or replaced with role-agnostic equivalents.

**Specific known surviving branches (to be confirmed by scanner):**
- Dashboard role-based listing section ordering (`if user.role == Role.BUYER: show demand first`)
- Any `context['is_buyer']` / `context['is_supplier']` template context variable injection

These are replaced by injecting listing counts directly (e.g., `supply_listing_count`, `demand_listing_count`) without role assumptions.

## Phase 2: Compliance Scanner Implementation

### `TemplateLanguageComplianceScanner`

**Location:** `marketplace/migration_control/ui_compliance.py`

**Scan targets:**
1. All `.html` files under `templates/marketplace/`, `templates/includes/`, and `templates/registration/` (recursive)
2. `marketplace/views.py`
3. `marketplace/forms.py`

**Violation patterns (FAIL — affect `passed` return value):**

| Pattern | Type |
|---|---|
| `user.role` in template expression | Silent dead code |
| `request.user.role` in template expression | Silent dead code |
| `{% if ... role ... %}` block | Silent dead code |
| `"Register as Buyer"` / `"Register as Supplier"` | Role language |
| `"Buyer Dashboard"` / `"Supplier Dashboard"` | Role language |
| `"Buyer listing"` / `"Supplier listing"` (role-identity usage) | Role language |
| `Role.BUYER` / `Role.SUPPLIER` in Python files | Dead import |
| `user.role` in Python files | Dead attribute |

**Warning patterns (reported separately — do NOT affect `passed` return value):**

| Pattern | Type |
|---|---|
| `role` in an HTML comment or Python docstring | Role language in comment |

Warnings appear in scanner output under a separate `warnings:` key but do not cause `passed=False`. This allows informational notes without blocking gates.

**Exclusions:**
- Test files (`*/tests/*`, `test_*.py`)
- Migration files (`*/migrations/*`)

**Return contract:**
```python
def scan(self) -> tuple[bool, list[str]]:
    """
    Returns (passed, violations).
    Each violation entry: "path/to/file.html:42 — pattern 'user.role' found"
    passed=True only when violations (FAIL-severity) is empty.
    Warnings are surfaced separately and do not influence passed.
    """
```

### `ParityValidator.validate_ui_language()`

Delegates to `TemplateLanguageComplianceScanner.scan()`. Produces a `ParityReport` with `scope="ui"`.

### `migration_validate --scope ui`

Adds `"ui"` to the `--scope` choices. Outputs:
```
ui: passed=True failures=0 summary=
```
or lists violations if any. `--fail-on-error` causes non-zero exit on failures.

## Post-Cleanup Testing Strategy

### Active Canonical Tests (tagged `@tag('ui_derolification')`)

These tests replace retired role-based UI assertions:

| Test | What it verifies |
|---|---|
| `test_signup_renders_no_role_field` | GET signup page — no role input in HTML |
| `test_signup_create_account_heading` | Page contains "Create Account" |
| `test_navbar_shows_supply_and_demand_for_any_user` | Both nav items visible regardless of listing history |
| `test_dashboard_heading_is_dashboard` | Page title/heading is "Dashboard" |
| `test_profile_shows_both_listing_sections` | Profile page has both Supply and Demand sections |
| `test_no_page_contains_buyer_supplier_role_label` | Smoke test: none of the key pages return "Buyer Dashboard" or "Supplier Dashboard" |
| `test_compliance_scanner_zero_violations` | `TemplateLanguageComplianceScanner` reports passed=True |

### Retired Migration-Era Tests

Tests that asserted role-based behavior (e.g., "supplier sees supply nav item only," "buyer denied supply_lot_list before Feature 4") are **retired**. Each retired test must either:
1. Be replaced by a canonical equivalent in `test_ui_derolification.py`, OR
2. Be commented out with a one-line explanation of which canonical test covers the same behavior.

No test may be silently deleted without a documented replacement.

## Error Handling

| Error Type | Condition | Recovery |
|---|---|---|
| `PreconditionFailed: CP5 not achieved` | `MigrationState.checkpoint_order < 5` | Do not proceed; complete Feature 7 first |
| `PreconditionFailed: User.role still exists` | `User._meta.get_field('role')` does not raise | Do not proceed; Feature 7 migration not applied |
| `ComplianceScanViolation` | Scanner finds role language post-Phase 1 | Fix violation; re-run scanner before Phase 2 sign-off |
| `RetiredTestWithoutReplacement` | Deleted test has no documented replacement | Add replacement or comment before merge |

## Scope Boundaries

- **In scope:** Template language, nav structure, profile role-agnostic layout, signup cleanup, compliance scanner, `migration_validate --scope ui`.
- **Out of scope:** Profile image upload (`profile-and-image-improvements`), email verification (`email-verification`), URL restructuring, radius filtering, listing expiry, operator tools, skin/CSS changes beyond what is needed to support derolified layouts.
