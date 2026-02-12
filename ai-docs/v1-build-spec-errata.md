# V1 Build Spec Errata / Clarifications

This document clarifies minor inconsistencies found during pre-build validation.  
It does **not** change intent; it only removes ambiguity.

Authority: This errata is a human-authored clarification to be applied alongside `ai-docs/v1-agent-build-spec.md`.

---

## 1) User Role vs Admin

- The build spec mentions three roles (buyer, supplier, admin).
- The User schema role enum lists `buyer | supplier` only.

**Clarification:** In V1, “admin” is not a selectable public user role.  
Admin capability is provided via Django’s built-in administration permissions (`is_staff` / `is_superuser`) and Django Admin.

---

## 2) Implementation Decisions Document

Execution agents must treat `ai-docs/v1-implementation-decisions.md` as an authoritative engineering tie-breaker (below the constitution, above ad-hoc agent choices).

---

END
