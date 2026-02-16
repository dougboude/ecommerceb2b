# CLAUDE.md — Standing Instructions for AI Agents

## First Step (Every Session)

Before doing any work in this repository, read and internalize:

1. `ai-docs/ai-constitution.md` — governance rules, scope control, stop conditions
2. `ai-docs/v1-agent-build-spec.md` — authoritative product spec and data schemas
3. `ai-docs/v1-implementation-decisions.md` — locked engineering decisions

## Authority Order

1. `ai-docs/v1-agent-build-spec.md` (highest)
2. `ai-docs/ai-constitution.md`
3. `ai-docs/v1-implementation-decisions.md`
4. Explicit human instructions in the current session (lowest)

If any planned work conflicts with a higher-authority document, **stop and ask the human** before proceeding. Do not silently override spec docs based on session instructions.

## Key Rules

- Do not add features not in the spec
- Do not alter the core loop, role boundaries, or data access rules without explicit approval
- Do not guess when requirements are ambiguous — ask
- Validate all planned changes against the build spec schemas before writing code
- When in doubt, do less, not more

## Tech Stack

- Python 3.12 / Django / PostgreSQL (SQLite for local dev)
- Server-rendered templates, no SPA
- Django ORM, Django built-in auth
- Virtual environment: `.venv/bin/python`
- Run Django commands with: `.venv/bin/python manage.py <command>`
