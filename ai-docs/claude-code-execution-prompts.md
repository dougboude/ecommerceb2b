# Claude Code – Execution Prompts (Django V1, Final)

These prompts are designed to be used **sequentially** by a human orchestrator.
Each prompt should be pasted into Claude Code one at a time.

Claude must not proceed to coding until Prompt 0 is satisfied.

---

## Required Documents (Authoritative)

Claude must load and respect **all** of the following documents before executing any work:

**Authority order (highest → lowest):**
1. `ai-docs/v1-agent-build-spec.md`
2. `ai-docs/ai-constitution.md`
3. `ai-docs/v1-implementation-decisions.md`
4. `ai-docs/v1-build-spec-errata.md`
5. Explicit human instructions in the current session

If any conflict exists, **stop and ask** rather than guessing.

---

## Prompt 0 – Context Anchor & Validation (MANDATORY)

You are acting as a senior Django engineer executing an agent-first build.

Before writing any code:
1. Read **all four** documents listed above.
2. Confirm explicitly that you understand and accept:
   - Stack: **Python 3.12 + Django + PostgreSQL**
   - UI: **Server-rendered templates**, no React, no SPA, no webpack
   - Background work: **No cron jobs, no Celery, no workers**
   - Expiration: **Lazy evaluation only**
   - Matching: **Must trigger buyer email notification**
   - Organizations (V1): **Exactly one buyer per organization**
   - Rate limiting: **Required on signup, login, messaging**
   - i18n: **All user-facing strings use Django gettext**
3. List any remaining ambiguities or conflicts.
4. Do **not** write code until ambiguities are resolved.

---

## Prompt 1 – Project Skeleton

Create a new Django project skeleton suitable for V1.

Requirements:
- Single Django project
- Single primary app (e.g., `marketplace`)
- PostgreSQL configuration via environment variables
- Production-hardened defaults (DEBUG off, secure cookies, ALLOWED_HOSTS placeholder)
- Container-friendly Linux deployment

Deliverables:
- Directory tree
- Key `settings.py` decisions
- Brief explanation of structure

---

## Prompt 2 – Core Models

Implement Django models that **exactly match** the build spec schemas and implementation decisions.

Must include:
- User (Django auth + country field)
- Organization (enforce one buyer per org in V1)
- DemandPost (with organization_id and created_by_user_id)
- SupplyLot
- Match (with notified_at)
- MessageThread
- Message

Rules:
- No extra fields
- Enforce Match uniqueness
- Use ForeignKeys explicitly
- Validation via Django where appropriate

---

## Prompt 3 – Matching Engine

Implement the V1 matching engine.

Requirements:
- normalize() and overlaps() exactly as specified
- Bidirectional matching (Supply↔Demand)
- Location compatibility rules (shipping bypass, country, radius, fallback)
- Quantity mismatch must not block matches
- Atomic creation of Match + MessageThread
- Trigger email notification on successful match creation

Deliverables:
- Pure Python matching logic
- Clear separation for unit testing

---

## Prompt 4 – Notifications

Implement email notifications.

Requirements:
- Buyer receives email on Match creation
- Prevent double sends using notified_at
- Dev backend: console or file
- Prod backend: SMTP via environment variables
- No third-party email SDKs

---

## Prompt 5 – Messaging

Implement messaging constrained by Matches.

Requirements:
- Threads exist only for Matches
- Only matched buyer/supplier may post
- No attachments
- No deletion or archiving in V1

---

## Prompt 6 – Views & Forms

Implement server-rendered views and Django forms for:
- Buyer DemandPost create/list
- Supplier SupplyLot create/list
- Match list
- MessageThread view

Rules:
- Django forms only
- Standard validation errors
- Offset pagination (25 default, 100 max)
- All strings wrapped for i18n

---

## Prompt 7 – Expiration Handling

Implement lazy expiration logic.

Requirements:
- Query helpers for “active” DemandPosts and SupplyLots
- No schedulers or background tasks
- Optional opportunistic status flipping allowed

---

## Prompt 8 – Rate Limiting

Implement rate limiting.

Requirements:
- Signup, login, messaging
- Use django-ratelimit
- Cache-backed using Django cache
- **V1 deployment assumes a single Django instance:** in-memory cache is acceptable for initial production
- Enforce thresholds defined in implementation decisions


---

## Prompt 9 – Tests

Write minimum sufficient tests.

Must include:
- Unit tests for normalize() and overlaps()
- Location compatibility tests
- Integration test:
  DemandPost + SupplyLot → Match → email sent → messaging allowed

Use Django’s built-in test framework only.

---

## Prompt 10 – Deployment Readiness

Prepare the app for deployment.

Deliverables:
- Example Dockerfile
- Required environment variables list
- Security checklist (cookies, secrets, debug flags)

No CI/CD setup required.

---

END
