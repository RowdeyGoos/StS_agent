# Phase 1 missing room capability workstreams

- **Date:** 2026-09-05
- **Coordinator:** Astra in the existing integration task.
- **Baseline:** `032b675c498ee2ad0beb94f2937b54fe7c47e78d` on
  `codex/phase1-actor-ready-integration`, in the user-selected 23cf checkout.
- **Authority:** the user explicitly requested parallel tasks to begin shops
  and other unsupported features. This selects repository development toward
  those capabilities. It does not enable new live controls or alter existing
  contracts by itself.
- **Status:** parallel contract proposals and synthetic acceptance design;
  production implementation follows coordinator review and contract freeze.

## Why these lanes

The targeted fresh event test reached one accepted event-choice receipt and
then `room_state_unsupported`. A separate cleanup inspection showed a loot
surface, consistent with an existing overlay guard. That does not prove the
specific unsupported cause, reconcile an effect, or classify the older timeout.
Shops remain deliberately unsupported. Useful next work separates item controls,
shop transactions, and the event parent lifecycle before joining them.

Read AGENTS.md and its linked documents, especially the current status,
actor-ready execution plan and acceptance ledger, bridge README, DECISIONS.md,
and MULTI_AGENT_EXECUTION.md. This document selects a new repository-only
preparation slice after the completed implementation packets; historical live
requests and old exclusions are not new operational authority.

## Ownership and first deliverables

Each visible task uses its own worktree created from the integration branch,
never local main. The initial producer contract remains `live_probe_v0`, bridge
0.8.0; existing room/reward decisions, receipts, diagnostic outputs and
`headless_v0` are read-only. Each lane owns only its named new proposal document.
No lane edits production, contracts, vectors, exports, dependencies or shared
documentation in this first packet.

| Task | Exclusive output | Scope |
| --- | --- | --- |
| MR-SHOP-01 | `docs/research/PHASE_1_SHOP_CAPABILITY_PROPOSAL.md` | Shop inventory, prices, availability, purchase/card-removal/leave action candidates; transaction identity and uncertainty constraints; select the smallest useful vertical slice. |
| MR-LOOT-02 | `docs/research/PHASE_1_ITEM_REWARD_CAPABILITY_PROPOSAL.md` | Public relic/potion reward choices, collection/skip, full potion inventory and replacement boundaries; parent-independent completion and the smallest useful reward slice. |
| MR-EVENT-03 | `docs/research/PHASE_1_EVENT_CONTINUATION_PROPOSAL.md` | Public event descriptions versus keys/flags, safe-provider limits, event steps, event-to-map completion and explicit child-screen handoff; parent lifecycle only, consuming future item controls rather than duplicating them. |

Dependencies between initial proposals are advisory. Production consumers have
hard dependencies on the reviewed, frozen relevant contracts. Shared modal
routing, wire/version changes, action/receipt identity and cross-phase
completion have exactly one owner: the coordinator. Item controls belong to the
loot lane; the event lane may propose how to enter/return from that child but
may not independently define collection, replacement or skip semantics.

## Shared questions to resolve before implementation

Independent review identified three common seams for coordinator resolution:
parent/child lineage and completion; cross-component reservation, uncertainty
and action accounting; and shop payment/acquisition behavior when a purchase
opens an item or overflow screen. Each proposal must address its side without
silently choosing the shared contract. In particular, resolving a child cannot
by itself prove enclosing event, reward, shop or room completion. Screen
disappearance alone is insufficient. Preserve no-retry behavior and account
for each accepted action once across a handoff.

Shop proposals must distinguish public slot identity from private instance IDs,
and investigate debit/acquisition ordering rather than assume atomic game APIs.
Loot proposals distinguish replacing an owned potion from declining an offered
item, and do not infer legal skip actions. Event proposals distinguish public
rendered information from unavailable structured effects or private state.
Include revalidation, passive reads, overlay races and bounded execution in
acceptance specifications. Treasure-room control, boss/act transitions, rest
upgrade submodals, nested combat choices, potion use/discard, card-reward redesign
and generic modal refactoring remain outside these first packets.

## Required evidence and handoff

Each task must produce a focused local commit with its owned proposal and:

1. A source-linked inventory of existing support and exact missing boundaries.
   Separate repository facts, existing sanitized static evidence and unknowns.
   Do not assert unobserved target-game APIs or use invented game semantics.
2. A minimal proposed public observation, legal action and receipt/completion
   contract, explicitly marked proposed. Identify producers, consumers, version
   impact, alternatives, exclusions and rollback/fail-closed behavior.
3. A synthetic acceptance matrix with concrete positive, stale/rejected,
   uncertain receipt, duplicate, changing screen/inventory, malformed input,
   hidden-information and cleanup cases. Match expected stopping behavior to
   the proposed scope; an accepted receipt is not completion or reconciliation.
4. A dependency-ordered implementation plan with exact proposed file ownership,
   smallest useful first slice, integration gates and independent review points.
5. The exact fresh game screen a future coordinator test would require, so the
   user can prepare the intended boundary without blind route exploration.
6. A concise handoff: commit, files, evidence/checks actually run, limitations,
   unresolved contract decisions, and model/effort and aggregate telemetry only
   if available. Never invent unavailable metrics.

No test implementation should merely encode an unreviewed assumption. Initial
acceptance matrices are specifications, not passing runtime evidence. Read-only
repository checks can substantiate facts; no game installation, credentials or
local profile access is needed. If repository evidence is insufficient, name
the precise missing fact for a later bounded static discovery decision.

## Operational and integration limits

Workers do not launch or operate the game, install/build against the live game,
read endpoints or credentials, access profile/save files, alter Steam Cloud,
retain live data, reconstruct discarded responses, retry uncertain actions,
or perform remote/destructive Git operations. They preserve existing user work.
Supported game operations remain coordinator-only under the user's existing
scope. No campaign is active. The user's waiver of repeated unmodded launch
checks remains in effect; normal quit and exact cleanup checks remain required.

The coordinator reviews the three proposals together, resolves common routing
and identity semantics, then freezes one coherent minimal implementation slice
before dispatching production writers and independent fixture reviewers. A
proposal commit alone neither enables a capability nor establishes live or
differential evidence. Existing accepted behavior and frozen contracts remain
unchanged until a reviewed successor explicitly replaces the affected boundary.
