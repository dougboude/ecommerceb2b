# AGENTS.md — Global Instructions for AI Agents

## First Step (Every Session)
1. Read `ai-docs/SESSION_STATUS.md` — current state, what's done, what's next.
2. Read `CLAUDE.md` — tech stack, services, rules, QA infrastructure.
3. Read `ai-docs/AGENT_NOTES.md` — gotchas, non-obvious patterns, hard-won lessons.

## Session Handoff Rules
- `ai-docs/SESSION_STATUS.md` is the **single canonical status tracker**.
- Update it at the end of any session that changes code, docs, or specs.
- Do not create new per-version status files.

## Scope & Authority
- Follow the authority order defined in `CLAUDE.md`.
- If instructions conflict, stop and ask before proceeding.
