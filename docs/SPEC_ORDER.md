# UX/UI Spec Creation and Implementation Order

Recommended order for generating and executing specs from `docs/FEATURE_BACKLOG.md`.

Ordering logic:
- dependency-safe sequencing
- strongest UX coherence gains early
- minimize rework/churn across templates and navigation

## Status Key
- `PLANNED` = backlog item defined, spec not yet created
- `REQ` = requirements drafted
- `DES` = design drafted
- `TASK` = tasks drafted
- `EXEC` = implementation in progress or complete

## Recommended Spec Order

1. **Navigation and Information Architecture Unification**
   - Why first: it is the structural shell for every user journey and page transition.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: none

2. **Cross-Page Feedback, Recovery, and Empty-State System**
   - Why second: creates consistent action/feedback contract reused by all later features.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Navigation and Information Architecture Unification`

3. **Account Access and Verification Journey**
   - Why third: user entry-state clarity reduces onboarding dead ends and informs navigation behavior.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Navigation and Information Architecture Unification`, `Cross-Page Feedback, Recovery, and Empty-State System`

4. **Discover Search Experience (Find Supply / Find Demand)**
   - Why fourth: primary discovery loop anchor; highest product-value interaction surface.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Navigation and Information Architecture Unification`, `Cross-Page Feedback, Recovery, and Empty-State System`

5. **Listing Detail Conversion Surface**
   - Why fifth: converts discovery traffic into meaningful actions (message/save) with context.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Discover Search Experience (Find Supply / Find Demand)`

6. **Messaging Workspace and Conversation Context**
   - Why sixth: central communication loop, depends on listing-driven conversation entry patterns.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Listing Detail Conversion Surface`

7. **Watchlist Follow-Up Workflow**
   - Why seventh: follow-up loop benefits from stabilized discover/listing/messaging surfaces.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Discover Search Experience (Find Supply / Find Demand)`, `Listing Detail Conversion Surface`, `Messaging Workspace and Conversation Context`

8. **Supply and Demand Listing Management Hub**
   - Why eighth: improves operational listing workflows after core discovery/communication loop is stabilized.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Navigation and Information Architecture Unification`, `Cross-Page Feedback, Recovery, and Empty-State System`

9. **Listing Authoring and Edit Flows**
   - Why ninth: best implemented after listing management hub conventions are set.
   - Status: `REQ, DES, TASK, EXEC`
   - Depends on: `Supply and Demand Listing Management Hub`

10. **Profile and Trust Surfaces**
    - Why tenth: trust and identity polish should align with finalized listing/messaging surfaces.
    - Status: `REQ, DES, TASK, EXEC`
    - Depends on: `Listing Detail Conversion Surface`, `Messaging Workspace and Conversation Context`, `Navigation and Information Architecture Unification`

## Practical Execution Guidance

- Generate specs in this same order (requirements -> design -> tasks per feature).
- Keep each feature as a vertical slice (templates + view behavior + interaction + validation/tests).
- Treat accessibility and stable UI test selectors as required acceptance criteria in each spec, not as separate standalone specs.

## Non-UI Production Hardening Queue

11. **Security Cache Hardening (Redis for Lockout/Rate Limits/Sessions)**
   - Why: security controls are currently cache-backed and must be consistent across workers/instances before production.
   - Status: `PLANNED`
   - Depends on: deployment/runtime architecture decision for managed Redis

## Messaging Workspace Re-Architecture Queue

12. **messaging-workspace-layout-and-navigation**
   - Why first: establishes the hybrid workspace shell and responsive navigation contract that all later messaging layers depend on.
   - Status: `REQ, DES, TASK`
   - Depends on: `Messaging Workspace and Conversation Context`, `Navigation and Information Architecture Unification`

13. **messaging-conversation-list-ia**
   - Why second: defines row information architecture and preview semantics required before real-time and grouping behaviors can be finalized.
   - Status: `REQ, DES, TASK`
   - Depends on: `messaging-workspace-layout-and-navigation`

14. **messaging-thread-pane-redesign**
   - Why third: defines the thread pane UX and dual-rendering contract required for split-pane interaction and direct navigation compatibility.
   - Status: `REQ, DES, TASK`
   - Depends on: `messaging-workspace-layout-and-navigation`

15. **messaging-sse-event-contract-expansion**
   - Why fourth: expands payload contract needed for dynamic row/group creation and coherent live workspace updates.
   - Status: `REQ, DES, TASK`
   - Depends on: `messaging-conversation-list-ia`, `messaging-thread-pane-redesign`

16. **messaging-realtime-workspace-orchestration**
   - Why fifth: implements client-side orchestration once event schema and workspace/list contracts are defined.
   - Status: `REQ, DES, TASK`
   - Depends on: `messaging-sse-event-contract-expansion`, `messaging-workspace-layout-and-navigation`, `messaging-conversation-list-ia`

17. **messaging-listing-grouped-conversations**
   - Why sixth: adds seller-focused listing grouping after flat-list IA and realtime orchestration are stable.
   - Status: `REQ, DES, TASK`
   - Depends on: `messaging-conversation-list-ia`, `messaging-realtime-workspace-orchestration`
