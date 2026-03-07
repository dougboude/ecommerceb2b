# AGENTS.md — Global Instructions for AI Agents

## First Step (Every Session)

**Orientation (read once when new to the project):**
1. Read `README.md` — what this product is and who it's for.
2. Read `ai-docs/PRODUCT_ROADMAP.md` — what's been built and where it's going.

**Every session:**
3. Read `ai-docs/SESSION_STATUS.md` — current state, what's done, what's next.
4. Read `CLAUDE.md` — tech stack, services, rules, QA infrastructure.
5. Read `ai-docs/AGENT_NOTES.md` — gotchas, non-obvious patterns, hard-won lessons.

**QA work only:**
6. Read `qa/README.md` — test scripts, seed accounts, reset tooling.

## Session Handoff Rules
- `ai-docs/SESSION_STATUS.md` is the **single canonical status tracker**.
- Update it at the end of any session that changes code, docs, or specs.
- Do not create new per-version status files.

## Scope & Authority
- Follow the authority order defined in `CLAUDE.md`.
- If instructions conflict, stop and ask before proceeding.
