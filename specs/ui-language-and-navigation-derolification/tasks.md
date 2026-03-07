# Implementation Plan

## Pre-Execution Gate Checklist

Before any task begins, the executing agent MUST confirm all four gates pass and document the output:

```python
# Gate 1 — CP5 confirmed
manage.py shell -c "
from marketplace.migration_control.state import get_or_create_state
s = get_or_create_state()
assert s.checkpoint_order == 5, f'CP5 required, got CP{s.checkpoint_order}'
print('Gate 1 OK — CP5 confirmed')
"

# Gate 2 — User.role absent
manage.py shell -c "
from marketplace.models import User
from django.core.exceptions import FieldDoesNotExist
try:
    User._meta.get_field('role')
    raise AssertionError('User.role still exists — block execution')
except FieldDoesNotExist:
    print('Gate 2 OK — User.role absent')
"

# Gate 3 — Legacy models absent
manage.py shell -c "
try:
    from marketplace.models import Organization, DemandPost, SupplyLot
    raise AssertionError('Legacy models still importable — block execution')
except ImportError:
    print('Gate 3 OK — legacy models absent')
"

# Gate 4 — Cutover-stage parity reports exist and passed
manage.py shell -c "
from marketplace.migration_control.parity import ParityReport
cutover_reports = ParityReport.objects.filter(stage='cutover')
assert cutover_reports.exists(), 'No cutover-stage parity reports found — run legacy-schema-cleanup-and-final-cutover first'
failed = cutover_reports.filter(passed=False)
assert not failed.exists(), f'Cutover-stage failures: {list(failed.values_list(\"scope\", flat=True))}'
print(f'Gate 4 OK — {cutover_reports.count()} cutover parity reports, all passed')
"
```

If any gate fails, STOP. Do not proceed with Phase 1 tasks.

---

## Phase 1: Convergence (Reversible)

### Group 1 — Signup and Onboarding Cleanup

- [ ] 1.1 Audit `marketplace/forms.py` `SignupForm` for any surviving `role` field assignment
  - Remove `role` from `Meta.fields` if present
  - Remove `user.role = ...` from `save()` if present
  - Remove `Role` import from `forms.py` if present
  - _Requirements: 5.2, 5.4_

- [ ] 1.2 Audit `templates/registration/signup.html`; fix if violations found
  - Confirm `<h1>` / page heading reads `Create Account` — update if not
  - Confirm submit button label reads `Create Account` — update if not
  - Confirm no copy reads `Register as Buyer`, `Register as Supplier`, or role-selection instructions — remove if found
  - Confirm no role radio/select input is rendered
  - _Requirements: 5.1, 5.3, 5.5_

- [ ] 1.3 Audit `templates/registration/login.html` for role-based language
  - No changes expected; confirm with scanner output
  - _Requirements: 2.1, 2.2_

### Group 2 — Navigation Derolification

- [ ] 2.1 Audit `templates/includes/_navbar.html` for all `user.role` references
  - Identify every `{% if user.role == ... %}` block
  - Document which nav items are currently hidden from each role group due to silent no-op
  - _Requirements: 3.3, 7.2_

- [ ] 2.2 Replace role-conditional nav with role-agnostic nav in `templates/includes/_navbar.html`
  - Remove all `{% if user.role ... %}` blocks
  - Render Supply, Demand, and Watchlist links unconditionally for all authenticated users
  - Structure Supply/Demand as "Your Listings" group with sub-items (or adjacent links — implementation choice)
  - Retain Messages badge (unread count — implemented in prior spec)
  - Retain Watchlist link (existing feature — must not be removed)
  - Final nav items: Dashboard, Discover, Messages [N], Watchlist, Your Listings (Supply, Demand), Profile
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 2.3 Audit `templates/marketplace/base.html` for any role-conditional blocks
  - Remove any `{% if user.role ... %}` wrapper found at the base level
  - _Requirements: 2.2, 3.3_

### Group 3 — Dashboard Derolification

- [ ] 3.1 Audit `templates/marketplace/dashboard.html` for role-based headings and section conditionals; fix if violations found
  - Identify any `{% if user.role ... %}` blocks — remove if present
  - Identify "Buyer Dashboard" / "Supplier Dashboard" heading text — replace with `Dashboard` if present
  - _Requirements: 2.4, 7.2_

- [ ] 3.2 Verify `templates/marketplace/dashboard.html` target state; update only what deviates
  - `<title>` must be `Dashboard — NicheMarket` (or site title variable) — update if not
  - Primary `<h1>` or heading must be `Dashboard` — update if not
  - Both supply and demand listing activity must render unconditionally — remove any role guard if present
  - _Requirements: 2.1, 2.4_

- [ ] 3.3 Audit `dashboard` view in `marketplace/views.py`; fix surviving role branches if found
  - Remove any `if user.role == Role.BUYER:` / `if user.role == Role.SUPPLIER:` display branching
  - Remove any `context['is_buyer']` / `context['is_supplier']` injection
  - Ensure `supply_listings` and `demand_listings` context variables are passed directly (queried from `Listing` model by type)
  - _Requirements: 2.2, 2.4_

### Group 4 — Profile Page Derolification

- [ ] 4.1 Audit `profile` view in `marketplace/views.py`; fix if role usage found
  - Scope: self-profile only (`/profile/` — authenticated user's own profile; no `profile_user` argument)
  - Remove any `user.role` read or role-based query path if present
  - Ensure `supply_listings = Listing.objects.filter(created_by_user=request.user, type=ListingType.SUPPLY, status=ListingStatus.ACTIVE)` is passed to context
  - Ensure `demand_listings = Listing.objects.filter(created_by_user=request.user, type=ListingType.DEMAND, status=ListingStatus.ACTIVE)` is passed to context
  - Ensure `member_since = request.user.date_joined` is passed to context
  - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [ ] 4.2 Audit `templates/marketplace/profile.html`; fix if violations found
  - Confirm display name, organization name (if set), location (country/locality), member since are rendered
  - Confirm profile image placeholder (styled initial or generic avatar) is rendered — no upload functionality
  - Confirm Supply Listings section renders with empty-state if no listings
  - Confirm Demand Listings section renders with empty-state if no listings
  - Remove any `{% if user.role ... %}` conditional that shows/hides a listing section if found
  - Remove any role label if found
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 9.2_

### Group 5 — Listing Form and Detail Label Cleanup

- [ ] 5.1 Audit `templates/marketplace/supply_lot_form.html`; fix if violations found
  - Confirm heading is `New Supply Listing` (create) / `Edit Supply Listing` (edit) — update if not
  - Confirm `<title>` tag matches heading — update if not
  - Remove any "Supplier" role label from the page if found
  - _Requirements: 2.1, 2.5_

- [ ] 5.2 Audit `templates/marketplace/demand_post_form.html`; fix if violations found
  - Confirm heading is `New Demand Listing` (create) / `Edit Demand Listing` (edit) — update if not
  - Confirm `<title>` tag matches heading — update if not
  - Remove any "Buyer" / "Wanted" role label from the page if found
  - _Requirements: 2.1, 2.5_

- [ ] 5.3 Audit `templates/marketplace/supply_lot_list.html` and `templates/marketplace/demand_post_list.html`; fix if violations found
  - Confirm headings are `Supply Listings` and `Demand Listings` respectively — update if not
  - Remove any role-identity heading ("Your Supply Lots as Supplier", etc.) if found
  - _Requirements: 2.1, 2.5_

- [ ] 5.4 Audit `templates/marketplace/supply_lot_detail.html` and `templates/marketplace/demand_post_detail.html`; fix if violations found
  - Remove any role-identity labels from detail headings or meta if found
  - _Requirements: 2.1_

### Group 6 — Remaining Python View Audit

- [ ] 6.1 Audit all view functions in `marketplace/views.py` for surviving `user.role` display references; fix if found
  - Exact search: `user.role`, `request.user.role`, `Role.BUYER`, `Role.SUPPLIER`
  - Scope: production view functions only (not test helpers or management commands)
  - If any found: replace role-conditional display logic with ownership-based or listing-type-based equivalents
  - Document any references found with file:line; confirm zero remaining after fixes
  - _Requirements: 2.2, 7.1_

- [ ] 6.2 Confirm `Role` enum is no longer imported in `marketplace/views.py` or `marketplace/forms.py`
  - If `Role` import remains but is unused after prior steps, remove it
  - _Requirements: 2.2, 6.3_

---

## Phase 1 Gate — Before Proceeding to Phase 2

Run the following before beginning Phase 2. All must pass:

```
# 1. Full test suite
manage.py test marketplace --verbosity=1
# Expected: all tests pass, 0 failures

# 2. UI compliance scanner (pre-implementation — scanner not yet wired, run manually)
# Review Phase 1 changes for any remaining role patterns before implementing scanner
```

If any test fails after Phase 1, fix the regression before proceeding. Do not carry failing tests into Phase 2.

---

## Phase 2: Compliance Scanner and Verification Lock

### Group 7 — Implement TemplateLanguageComplianceScanner

- [ ] 7.1 Create `marketplace/migration_control/ui_compliance.py`
  - Implement `TemplateLanguageComplianceScanner` class
  - `scan()` method: returns `(passed: bool, violations: list[str])`
  - Scan scope: all `.html` files under `templates/marketplace/` (recursive)
  - Scan scope: `marketplace/views.py`, `marketplace/forms.py`
  - Exclude: all files matching `*/tests/*`, `test_*.py`, `*/migrations/*`
  - Violation patterns (see design doc): `user.role`, role-label strings, `Role.BUYER/SUPPLIER` imports
  - Each violation entry: `"relative/path/to/file.html:42 — found 'user.role'"`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7.2 Add `validate_ui_language()` to `marketplace/migration_control/parity.py`
  - Delegates to `TemplateLanguageComplianceScanner().scan()`
  - Returns `ValidationResult`
  - _Requirements: 6.6_

- [ ] 7.3 Add `"ui"` scope to `marketplace/management/commands/migration_validate.py`
  - Add `"ui"` to `--scope` choices list (alongside `counts`, `relationships`, `identity`, `listing`, `permission`)
  - Call `validator.validate_ui_language()` when scope is `"ui"` or `"all"`
  - Emit report: `ui: passed=True failures=0 summary=`
  - _Requirements: 6.6, 6.7_

- [ ] 7.4 Run `manage.py migration_validate --scope ui --fail-on-error`
  - Must produce: `ui: passed=True failures=0 summary=`
  - If violations found: return to Phase 1 and resolve before continuing
  - This is the **hard Phase 2 gate** — do not proceed past this task until it passes
  - _Requirements: 6.6, 6.7, 7.1_

### Group 8 — No Hidden Compatibility Fallback Pass

- [ ] 8.1 Review all templates for `{% if user.role is not None %}`, `{% if user.role %}`, `{% with role=user.role %}` patterns
  - If any found: add to violation list in scanner and fix before proceeding
  - _Requirements: 7.2, 7.3_

- [ ] 8.2 Confirm no template uses `hasattr(user, 'role')` or equivalent Python-in-template guard
  - Django templates don't support `hasattr` directly, but check for custom template tags or `{% if user|has_attr:"role" %}` patterns
  - _Requirements: 7.2_

- [ ] 8.3 Document any intentional exception where role-adjacent language is preserved
  - Add `{# INTENTIONAL: ... reason ... #}` comment in template for each exception
  - If no exceptions exist, confirm with comment in task completion notes
  - _Requirements: 7.4_

### Group 9 — Tests

- [ ] 9.1 Create `marketplace/tests/test_ui_derolification.py`
  - All tests tagged `@tag('ui_derolification')`
  - Use `@override_settings(STORAGES=...)` for static file safety (same pattern as `test_permission_policy.py`)
  - _Requirements: 8.1_

- [ ] 9.2 Write `test_signup_renders_no_role_field`
  - GET `/signup/` — assert response does not contain a `<select name="role">` or `<input name="role">`
  - Assert page contains "Create Account"
  - _Requirements: 5.1, 5.3, 8.1_

- [ ] 9.3 Write `test_signup_heading_is_create_account`
  - GET `/signup/` — assert page contains heading text "Create Account"
  - Assert page does not contain "Register as Buyer" or "Register as Supplier"
  - _Requirements: 5.3, 8.1_

- [ ] 9.4 Write `test_navbar_shows_supply_and_demand_for_all_authenticated_users`
  - Log in as a user with no listings
  - GET any page that renders the navbar
  - Assert response contains link to `supply_lot_list` URL
  - Assert response contains link to `demand_post_list` URL
  - _Requirements: 3.1, 3.2, 8.1_

- [ ] 9.5 Write `test_dashboard_heading_is_not_role_labeled`
  - Log in as any user
  - GET dashboard URL
  - Assert "Buyer Dashboard" not in response content
  - Assert "Supplier Dashboard" not in response content
  - _Requirements: 2.4, 8.1_

- [ ] 9.6 Write `test_profile_shows_both_listing_sections`
  - Create a user with one supply listing and one demand listing
  - GET profile URL for that user
  - Assert response contains "Supply Listings" section
  - Assert response contains "Demand Listings" section
  - _Requirements: 4.2, 4.3, 8.1_

- [ ] 9.7 Write `test_compliance_scanner_zero_violations`
  - Instantiate `TemplateLanguageComplianceScanner`
  - Call `scanner.scan()`
  - Assert `passed is True`
  - Assert `violations == []`
  - _Requirements: 6.2, 8.3_

- [ ] 9.8 Identify and retire stale migration-era tests that asserted role-based UI behavior
  - Search existing tests for: `"Buyer Dashboard"`, `"Supplier Dashboard"`, `role == Role.BUYER` in response assertions, role-gated nav assertions
  - For each found test: either update to test canonical behavior, or add retirement comment explaining replacement
  - _Requirements: 8.2, 8.4_

### Group 10 — Final Verification Checkpoint

- [ ] 10.1 Run full test suite
  ```
  manage.py test marketplace --verbosity=1
  ```
  Expected: all tests pass. Zero failures. Zero errors.
  _Requirements: 8.1_

- [ ] 10.2 Run UI compliance gate
  ```
  manage.py migration_validate --scope ui --fail-on-error
  ```
  Expected: `ui: passed=True failures=0 summary=`
  _Requirements: 6.6, 7.1_

- [ ] 10.3 Confirm scope boundaries — no unrelated features included
  - No profile image upload code added
  - No email verification code added
  - No URL pattern changes
  - No radius filtering, listing expiry, or operator tools
  - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6_

- [ ] 10.4 Update `specs/SPEC_ORDER.md` status to `REQ, DES, TASK, EXEC`
  - Update `ai-docs/SESSION_STATUS.md` with implementation summary
