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

## Proposal handoffs

### 2026-09-05 — Shop proposal recovered and reviewed

The user reported that the shop task completed its proposal but failed to
convey the handoff. The coordinator recovered it directly from the clean
`codex/mr-shop-01` worktree at local source commit
`e3dc78fd493a4b3a1aa678e9d851faf8e992c23f`; no work was lost. Its sole new
[shop proposal](research/PHASE_1_SHOP_CAPABILITY_PROPOSAL.md) was integrated as
`46ba208`, then amended by the coordinator following independent review.

The proposal is accepted as **reviewed design input, still proposed and
unfrozen**. Its first candidate slice is passive visible-shop observation, one
affordable ordinary-card purchase and explicit leave. Relic/potion purchases
and card removal remain later slices. Exact target members, passive access,
transaction ordering, stock disposition, leave evidence and shared handoff/
version/output decisions still require the declared static and contract gates.

Independent review required pending facts and reservation before dispatch,
separate producer reservation and host receipt/reconciliation counts, exact
post-purchase slot evidence rather than revision alone, and conditional future
partial-prefix output. The coordinator applied these corrections. The source
claims and lane boundaries otherwise passed review. All 16 relative source
links resolve; the local commit and amended diff pass whitespace checks.
The 30 acceptance cases are specifications, not executed tests. Production,
wire, artifacts and live capability remain unchanged; no game action occurred.

### 2026-09-05 — Event and item proposals recovered and reviewed

The coordinator checked the other two worktrees after the user's follow-up.
Both were clean and contained a completed sole-document commit:

- `MR-EVENT-03`, source `4295251c809122473be99b4b76999fb2c5d0f318`,
  locally integrated as `bdbce8f`:
  [event proposal](research/PHASE_1_EVENT_CONTINUATION_PROPOSAL.md).
- `MR-LOOT-02`, source `c583d24df7aa109d07e66671a26c8c03b5f21b1f`,
  locally integrated as `3e0e0e6`:
  [item proposal](research/PHASE_1_ITEM_REWARD_CAPABILITY_PROPOSAL.md).

Independent review of each proposal required coordinator amendments. The event
proposal now describes current D47 map/absence/identity behavior accurately and
requires authoritative parent-progression evidence before a new step identity
can renew an old option. Child completion and repeated matching reads alone are
insufficient. Existing changed-projection hashes remain available, while a
returning reserved projection cannot evade replay rejection. It separates the
producer reservation budget from host receipt counts, intentional transient
public text from forbidden/persisted output, and a proposed typed combat
handoff from the existing combat client.

The item proposal now installs pending facts with reservation before dispatch,
suppresses fresh actions while pending, separates producer budgets from host
counts, and requires exact inventory invariants. Same-ID replacement needs an
independent public witness; final-result correlation remains a blocking shared
contract decision. Player-visible information is distinguished from merely
CLR-public members. Failure-output changes require an explicit successor
contract. Six additional specifications cover pending races, replay, inventory,
same-ID replacement, correlation and private-identity leakage.

All three proposals are now **reviewed design input, still proposed and
unfrozen**. The event document has 38 specified cases and 11 resolving relative
links; the item document has 45 specified cases and 18 resolving relative links.
These are documentation/link/uniqueness checks, not executable or live evidence.
No production tests were rerun for these docs-only integrations. Production,
wire, package pins and the last live cleanup state remain unchanged.

The next dependency is one bounded static-source scope resolving exact item
controls/inventory and event text/progression/exit members, plus shop access and
purchase/leave facts. Shared routing, result correlation, parent/child ownership
and protocol/output versions must be frozen before production consumers begin.
The proposed first item slice is direct relic collection and potion collection
into an empty slot; event-to-item continuation depends on that reviewed child
component. No current game setup or additional live action is required for this
proposal handoff.

### 2026-09-05 — Static facts accepted; isolated item contract frozen

The coordinator completed the [bounded API scope](PHASE_1_MISSING_ROOM_API_SCOPE.md)
against the pinned immutable images. The [sanitized result](research/PHASE_1_MISSING_ROOM_API_RESULT.md)
and [exact selections](research/PHASE_1_MISSING_ROOM_API_SELECTION.json) cover
47 types and 102 actual method bodies, with independent item/event/shop reviews.
No game code executed. The shop proposal now reflects acquisition before debit,
conditional restock, and separate inventory-close and room-leave actions. Exact
shop dispatch/back/FTUE control connections remain unfrozen static gates. Event
final-page state and actual exit are distinct; generic lineage-safe progression
was not found. These findings supersede broader assumptions in the proposals.

The [item V1 contract](PHASE_1_ITEM_V1_CONTRACT.md) is independently frozen for
one direct collection with exact retained result correlation. Its separate
`bridge/Sts2AgentBridge/successors/item_v1` tree is the sole implementation
owner's write boundary; the old src tree, artifact and live routes remain frozen.
Pure-core in-memory tests and a compile-only native adapter are authorized
under this repository gate. This replaces the earlier worker prohibition on
compiling against immutable game references for this exact item packet only;
it permits no game execution, installation or broader static discovery.

Implementation and final review are tracked in the
[missing-room acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md).
No user game setup is required until a later concrete live successor is ready.

The isolated item implementation subsequently passed all ten pure-core fixture
groups, independent aggregate review, the coordinator's fresh offline checker,
eleven mock-only runner boundary checks and bit-identical assembly comparison
across two fresh builds. Existing regression passed 1,112 tests and old 0.8.0
source identity is unchanged. The successor remains unselected: native adapter
evidence is compilation only, and routing/wire/host/package/live composition is
the next item dependency. See the acceptance ledger for exact hashes and limits.
