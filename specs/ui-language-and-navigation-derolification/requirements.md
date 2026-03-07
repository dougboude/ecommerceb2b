# Requirements Document

## Introduction

This spec removes all role-based language and role-conditional logic from the platform's templates, forms, navigation, and Python view surface. It delivers the role-agnostic UI defined in roadmap §§3.4, 3.5, and 3.7. The result is a product where users see no reference to "buyer," "supplier," or role-based registration — only listing-type language (Supply / Demand) and ownership context (Your Listings).

This spec executes **exclusively at CP5** (post-legacy-cleanup). By the time this spec runs, `User.role`, `Organization`, `DemandPost`, and `SupplyLot` have been removed from the database and codebase by `legacy-schema-cleanup-and-final-cutover`. Any remaining template or Python reference to these constructs is dead code that silently misfires due to Django's template fault tolerance. This spec eliminates that silent dead code and replaces it with canonical role-agnostic surfaces.

## Migration State Assumptions

| Assumption | Required State | Fail Condition |
|---|---|---|
| Migration checkpoint | CP5 achieved | Block execution if `MigrationState.checkpoint_order < 5` |
| `User.role` field | Removed from DB | Block execution if `User._meta.get_field('role')` does not raise `FieldDoesNotExist` |
| `Organization` model | Removed from DB | Block execution if `Organization` can be imported from `marketplace.models` |
| `DemandPost` model | Removed from DB | Block execution if `DemandPost` can be imported from `marketplace.models` |
| Legacy parity gates | All passing at cutover stage | `migration_validate --scope all` must have produced passing cutover-stage reports |

**Hard gate artifact before Phase 1 begins:**
```
manage.py migration_validate --scope all --fail-on-error
# Must produce: all scopes passed at cutover stage
```

**Hard gate artifact before Phase 2 begins:**
```
manage.py migration_validate --scope ui --fail-on-error
# Must produce: ui scope passed (TemplateLanguageComplianceScanner returns 0 violations)
```

## Dependencies

- **Required predecessor spec:** `legacy-schema-cleanup-and-final-cutover` (`EXEC`)
- All other foundation specs (`1–6`) must also be `EXEC`.
- CP5 must be achieved in the migration control state machine before any task in this spec is executed.

## Glossary

- **Role-based Language**: Any UI string that refers to user identity through a marketplace role — "buyer," "supplier," "Register as Buyer," "Buyer Dashboard," etc.
- **Listing-type Language**: Role-agnostic alternatives — "Supply listing," "Demand listing," "Create Listing," "Your Listings."
- **Role-conditional Branch**: Any `{% if user.role ... %}` or `{% if request.user.role ... %}` block in a template, or any `if user.role` check in Python view code.
- **Canonical UI Surface**: The post-derolification version of a page or component — no role assumptions, no legacy fallbacks.
- **Compliance Scanner**: `TemplateLanguageComplianceScanner` — a scanner that inspects all production templates and Python view files for surviving role-based language patterns and silent dead code.
- **Silent Dead Code**: Template blocks that reference `user.role` which Django's template engine silently skips (returning empty string) rather than raising an error, masking defects.

## Requirements

### Requirement 1: Migration State Gate Enforcement

**User Story:** As a platform operator, I want this spec's execution gated behind confirmed CP5 state, so role-removal is never attempted while legacy data structures still exist.

#### Acceptance Criteria

1. WHEN this spec begins execution, THE System SHALL verify `MigrationState.checkpoint_order == 5` and fail with a clear message if not.
2. WHEN this spec begins execution, THE System SHALL verify `User._meta.get_field('role')` raises `FieldDoesNotExist`; if `role` still exists on the model, execution SHALL be blocked.
3. WHEN this spec begins execution, THE System SHALL verify `Organization`, `DemandPost`, and `SupplyLot` cannot be imported from `marketplace.models`; if any imports succeed, execution SHALL be blocked.
4. WHEN pre-execution checks pass, THE System SHALL run `migration_validate --scope all --fail-on-error` and confirm all gates pass before proceeding.

### Requirement 2: Remove Role-Based Language from All Templates

**User Story:** As a user of the platform, I want all pages to use role-agnostic language, so the product communicates in terms of listings and actions rather than buyer/supplier identity.

#### Acceptance Criteria

1. WHEN the derolification is complete, THE System SHALL have no template containing the literal strings `"buyer"`, `"Buyer"`, `"supplier"`, `"Supplier"` used as role-identity labels (e.g., "Buyer Dashboard," "Register as Supplier," "Supplier listing"). **Exception:** these words may appear in inline help text or descriptions only if they describe listing-type semantics (e.g., "this listing is seeking supply"), not user identity.
2. WHEN the derolification is complete, THE System SHALL have no template containing `user.role` or `request.user.role` in any expression, filter, or conditional.
3. THE System SHALL replace "Register as Buyer" and "Register as Supplier" with "Create Account" in `signup.html` and any linked copy.
4. THE System SHALL replace "Buyer Dashboard" and "Supplier Dashboard" with "Dashboard" in `dashboard.html` and the page `<title>` tag.
5. THE System SHALL replace "Create Supplier Listing" / "Create Wanted Listing" (and equivalent role-labeled create prompts) with "Create Listing → Supply" and "Create Listing → Demand" respectively.
6. IF the `TemplateLanguageComplianceScanner` reports any violation, THEN THE System SHALL block Phase 2 execution until all violations are resolved.

### Requirement 3: Update Navigation to Role-Agnostic Structure

**User Story:** As an authenticated user, I want navigation that reflects my actions and listings rather than my role, so the platform feels consistent with the role-agnostic architecture.

#### Acceptance Criteria

1. WHEN a user is authenticated, THE System SHALL render the following top-level navigation items: **Dashboard**, **Discover**, **Messages**, **Your Listings**, **Profile**. No role-conditional items shall appear.
2. THE **Your Listings** navigation item SHALL expand to or link to two sub-items: **Supply** (routes to supply listing list) and **Demand** (routes to demand listing list). Both sub-items SHALL be visible to all authenticated users regardless of whether they currently have listings of that type.
3. THE System SHALL remove any `{% if user.role == "buyer" %}` or `{% if user.role == "supplier" %}` conditional wrapping navigation items in `_navbar.html` or `base.html`.
4. THE System SHALL retain the "Messages N" unread badge on the Messages nav item (implemented in a prior spec).
5. WHEN the derolification is complete, THE `_navbar.html` template SHALL contain no reference to `user.role`.

### Requirement 4: Update Profile Page to Role-Agnostic Model

**User Story:** As a user viewing a profile, I want to see the profile owner's listing activity on both sides of the market, so I can understand the full picture of who I am dealing with.

#### Acceptance Criteria

1. WHEN a profile is viewed, THE System SHALL display: display name, optional organization name, location (country / locality when available), member since date.
2. WHEN a profile is viewed, THE System SHALL show a **Supply Listings** section listing the profile owner's active supply listings (type=SUPPLY, status=ACTIVE).
3. WHEN a profile is viewed, THE System SHALL show a **Demand Listings** section listing the profile owner's active demand listings (type=DEMAND, status=ACTIVE).
4. IF a section has no listings, THE System SHALL render an empty-state message (e.g., "No supply listings yet.") rather than hiding the section.
5. THE profile page SHALL NOT display `User.role` or any role-based label for the profile owner.
6. THE profile page SHALL display a profile image placeholder (a styled initial or generic avatar) when no image is uploaded. Full image upload is deferred to `profile-and-image-improvements`.

### Requirement 5: Update Signup and Onboarding Flows

**User Story:** As a new user, I want to register without selecting a role, so onboarding matches the role-agnostic product model.

#### Acceptance Criteria

1. WHEN a user registers, THE System SHALL present a single "Create Account" flow with no role selector field.
2. THE `SignupForm` SHALL NOT include a `role` field or any role-selection widget; any remaining role assignment in the form's `save()` method SHALL be removed.
3. THE signup template SHALL use the heading "Create Account" and the submit button label "Create Account".
4. THE System SHALL not set `user.role` during account creation; since `User.role` no longer exists (removed in Feature 7), no explicit removal is needed, but the form code path SHALL be verified clean.
5. IF any onboarding copy references "buyer" or "supplier" as a user identity choice, THE System SHALL replace it with listing-type language or remove it.

### Requirement 6: Template Language Compliance Scanner

**User Story:** As a maintainer, I want a compliance scanner that verifies all role-based language has been removed from production templates and view code, so regressions are detected automatically.

#### Acceptance Criteria

1. THE System SHALL implement `TemplateLanguageComplianceScanner` in `marketplace/migration_control/ui_compliance.py`.
2. THE scanner SHALL inspect all `.html` files under `templates/marketplace/` for the following violation patterns:
   - `user.role` or `request.user.role` in any template expression, filter, or conditional
   - Literal strings: `"Register as Buyer"`, `"Register as Supplier"`, `"Buyer Dashboard"`, `"Supplier Dashboard"`, `"Buyer listing"`, `"Supplier listing"` (case-insensitive)
   - Django template conditionals of the form `{% if ... role ... %}` in any combination
3. THE scanner SHALL inspect Python files in `marketplace/views.py` and `marketplace/forms.py` for:
   - `user.role` or `request.user.role` references
   - `Role.BUYER` or `Role.SUPPLIER` references
   - `from .models import ... Role ...` imports (or any import of `Role` from marketplace models)
4. THE scanner SHALL return `(passed: bool, violations: list[str])` where each violation includes the file path and line number.
5. THE scanner's scope SHALL be **production paths only** — test files are excluded.
6. THE System SHALL wire the scanner into `ParityValidator.validate_ui_language()` and expose it via `migration_validate --scope ui`.
7. IF `migration_validate --scope ui` produces failures, THE System SHALL treat that as a blocking gate for Phase 2 completion sign-off.

### Requirement 7: No Hidden Compatibility Fallback Pass

**User Story:** As a maintainer, I want explicit confirmation that no template silently skips a role-conditional block, so silent dead code cannot mask defects in production.

#### Acceptance Criteria

1. BEFORE Phase 2 is marked complete, THE System SHALL run `TemplateLanguageComplianceScanner` and confirm zero violations.
2. THE System SHALL verify that no template uses `{% if user.role is not None %}`, `{% if user.role %}`, `{% with role=user.role %}` or any equivalent pattern that would silently evaluate to falsy without raising an error.
3. IF any template contains a `{% if ... role ... %}` block that was left intact (even if it silently no-ops due to removed field), THE System SHALL flag it as a violation and require removal.
4. THE System SHALL document any intentional exception where role-adjacent language is preserved, with a comment in the template explaining why it is not a violation.

### Requirement 8: Post-Derolification Testing Strategy

**User Story:** As a quality owner, I want a clear distinction between active canonical tests and retired migration-era tests, so coverage does not degrade silently after cleanup.

#### Acceptance Criteria

1. THE System SHALL include **active canonical tests** tagged `@tag('ui_derolification')` that verify:
   - Signup renders without a role field
   - Navigation renders with "Your Listings → Supply / Demand" for all authenticated users
   - Profile page renders both Supply and Demand listing sections
   - No page title or heading contains "Buyer" or "Supplier" as role labels
2. THE System SHALL retire or update any existing tests that asserted role-based navigation behavior (e.g., "supplier sees supply nav," "buyer denied supply create"). **Retired tests must be replaced** by canonical equivalents testing the new behavior.
3. THE System SHALL include a test that verifies `TemplateLanguageComplianceScanner` returns zero violations against the production template set.
4. IF a previously passing test is removed without a replacement, THE System SHALL document the gap in the test file with a comment explaining what the new canonical test covers instead.

### Requirement 9: Scope Boundaries and Non-Goals

**User Story:** As a product owner, I want this spec tightly scoped to language and navigation derolification, so feature work is not bundled in.

#### Acceptance Criteria

1. THE System SHALL limit scope to: template language changes, navigation restructuring, profile page role-agnostic layout, signup flow cleanup, and compliance scanner implementation.
2. THE System SHALL NOT implement profile image upload (deferred to `profile-and-image-improvements`).
3. THE System SHALL NOT implement email verification (deferred to `email-verification`).
4. THE System SHALL NOT implement radius filtering, listing expiry, or operator tools.
5. THE System SHALL NOT change URL patterns or view function names (deferred to a post-launch cleanup spec).
6. IF requested changes are outside this scope, THE System SHALL defer them to the appropriate downstream spec.
