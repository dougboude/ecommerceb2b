# Implementation Plan

## Phase 1 — Contract Definition

- [ ] 1.1 Define final `new_message` payload schema for workspace needs.
- [ ] 1.2 Map schema fields to existing server model data sources.

## Phase 2 — Publisher Updates

- [ ] 2.1 Update SSE publisher to emit expanded schema.
- [ ] 2.2 Preserve existing fields used by current client logic.

## Phase 3 — Validation

- [ ] 3.1 Add tests for payload completeness and field formats.
- [ ] 3.2 Add regression tests ensuring existing consumers still function.
