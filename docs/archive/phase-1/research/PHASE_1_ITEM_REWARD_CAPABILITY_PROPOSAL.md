# Phase 1 item reward capability proposal

- **Task:** `MR-LOOT-02`
- **Date:** 2026-09-05
- **Proposal baseline:** `68c8b50eed05d5442c66cc55f9ec9cf0513c7009`
- **Status:** coordinator-review proposed input and synthetic acceptance
  specification, pending target-API discovery and coordinator contract freeze
- **Current contracts preserved:** bridge `0.8.0`, `live_probe_v0`, `headless_v0`,
  D47 room lifecycle, and every accepted default/provider
- **Authority:** repository-only proposal. This document does not authorize a
  production change, game build/install, launch, endpoint access, profile/save
  access, live action, or retained capture.

## 1. Recommendation

Add a logically separate **item decision component** for public relic and potion
offers. It should own only item-local observation and item-local controls:

- collect an offered relic;
- collect an offered potion when inventory has capacity;
- skip an offered item only when an exact, visible, enabled control is proved to
  decline that offer;
- on an explicitly identified full-potion child surface, replace one exact
  owned potion slot or decline the offered potion when the corresponding public
  controls are actually present.

The item component must be callable at a fresh item surface without knowing
whether a reward, event, shop, or another supported parent opened it. It may
report that its own accepted action reconciled. It may not report that an
enclosing reward, event, room, shop transaction, floor, or run completed.

The smallest useful first production slice should project relic and potion
offers but enable only:

1. direct relic collection; and
2. direct potion collection into a publicly observed empty potion slot.

Both require a recognized public offer, a mapped enabled control, an immediate
pre-click revalidation, and an exact item-inventory postcondition. Per-offer
skip is enabled only if static evidence establishes a distinct public skip
control. Potion replacement and decline use the same contract shape but remain
a second implementation sub-slice until the full-inventory surface and public
controls are established. A full inventory must never be treated as an empty
slot, an implicit discard, an automatic replacement, or permission to click the
offer and infer what followed.

This proposal recommends a separate logical component rather than extending
card-reward child semantics. The coordinator still owns the shared transport
route, protocol/version, parent-child lineage, arbitration, reservation and
aggregate-accounting decision. Production and consumer tests must not be
written against the illustrative wire spelling below until that review freezes
one shared interface.

## 2. Evidence classification

### 2.1 Repository facts

1. The current reward reader accepts at most eight visible `NRewardButton`
   targets, orders them by `RewardsSetIndex`, requires one player, and recognizes
   only `GoldReward` and `CardReward`. Every other populated reward becomes
   `PublicRewardKind.Unsupported` with no item identity or action
   ([reader](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardDecisionReader.cs#L413-L573),
   [DTO](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicRewardDecision.cs#L9-L24)).

2. The parent reward snapshot advertises claim/open for recognized unselected
   rewards and always advertises `proceed`; unsupported entries do not prevent
   that parent action
   ([reader](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardDecisionReader.cs#L224-L283)).
   Consequently, current `proceed` is not evidence of a per-item skip control.

3. The current reward child is specifically a card-selection screen. It maps
   visible card holders and advertises `skip_card` only when `CardReward.CanSkip`
   is true and a visible enabled alternative button is found
   ([reader](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardDecisionReader.cs#L286-L343),
   [action applier](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardActionApplier.cs#L93-L190)).
   Those APIs do not establish item skip or potion decline semantics.

4. Reward actions are snapshot-bound, checked against advertised action IDs,
   immediately reread before dispatch, reserved before the click/signal, bounded
   to 17 reserved dispatches per session and three sessions per process, and
   reconciled by a later read. A reserved decision ID cannot be reserved twice;
   post-reservation dispatch faults still consume the producer budget
   ([applier](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardActionApplier.cs#L26-L90),
   [session](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardInteractionSession.cs#L262-L399)).

5. The host reward client strictly validates exact object shapes, ordered reward
   indices, complete legal-action sets, exact action receipts, decision revision
   advancement and action-specific post-state. It separates accepted receipt
   from successful reconciliation
   ([host client](../../../../bridge/Sts2AgentBridge/tools/apply_reward_live.py#L134-L345),
   [transition checks](../../../../bridge/Sts2AgentBridge/tools/apply_reward_live.py#L381-L481),
   [D49](../../../../DECISIONS.md#d49-separate-reward-attempts-receipt-acceptance-and-reconciliation)).

6. The room reader marks any nonempty overlay stack as an unsupported room
   surface before event projection, as well as simultaneous room surfaces and a
   custom event node. It suppresses foreground-map room actions and does not infer
   event-to-map completion
   ([room reader](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomDecisionReader.cs#L43-L77),
   [room lifecycle](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomDecisionReader.cs#L289-L430),
   [D47](../../../../DECISIONS.md#d47-separate-room-identity-from-foreground-and-completion-evidence)).

7. `live_probe_v0` has exactly eleven routes. The surface verifier requires the
   exact route set and exact allowed game/Godot type/member closure. No relic,
   potion, item-inventory, item-screen or item-control type/member is currently
   allowed
   ([routes](../../../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/ProbeRoutes.cs#L11-L53),
   [surface policy](../../../../bridge/Sts2AgentBridge/contracts/live_probe_v0/forbidden_surface.json)).
   Adding a separate item route or target API therefore cannot be represented as
   an unchanged `live_probe_v0` / bridge `0.8.0` artifact.

8. The current status expressly excludes potion acquisition, replacement, use
   and discard. Relics and potions remain fail-closed in the current bounded run
   ([current status](../../../STATUS.md#current-exclusions),
   [D52](../../../../DECISIONS.md#d52-treat-elite-as-host-side-combat-without-expanding-the-bridge)).

### 2.2 Sanitized checked-in live evidence

One user-prepared fresh event produced one exact accepted event receipt followed
by `room_state_unsupported`. A separate read-only cleanup check showed a visible
potion-loot overlay. The retained diagnostic did not identify the unsupported
predicate, selected option, effect, overlay class, controls, item identity,
inventory state, or legal collect/skip action. No loot action was attempted
([acceptance ledger](PHASE_1_ACTOR_READY_ACCEPTANCE.md#2026-09-05--targeted-event-diagnostic-observed-unsupported-continuation)).

This supports prioritizing a parent-independent item child, but it is not an API
contract, a completed event, or item-control evidence.

### 2.3 Hypotheses that must not enter production or fixtures

It is plausible that the pinned game has distinct relic/potion reward models,
item model IDs, an inventory collection, a potion-overflow screen and clickable
controls analogous to current reward/card surfaces. The repository does not
establish their exact names, members, ordering or behavior. Names such as
`RelicReward`, `PotionReward`, “discard”, “replace”, or “skip” are descriptions
in this proposal, not claims about target types or methods.

### 2.4 Exact missing static facts

Before production assignment, a separately reviewed, bounded static-API packet
must establish all of the following from the pinned build without executing it:

1. concrete public runtime types that represent relic and potion offers, and the
   public stable definition ID for each offered item;
2. how a visible offer maps to one exact enabled UI control and which public
   operation dispatches it;
3. whether direct relic/potion collection is synchronous or opens a child, and
   which public state proves offer-local resolution;
4. the public owned-relic and potion-inventory accessors, potion capacity, slot
   order, empty-slot representation and maximum observed size;
5. the exact full-inventory child type, offered-potion accessor, owned-slot
   control mapping, replacement operation, and any distinct decline control;
6. whether any direct item-offer surface has a per-offer skip control; parent
   `Proceed`, screen disappearance and an unrelated close control are not enough;
7. stable display/order facts for mixed gold/card/relic/potion terminal rewards
   and for potion replacement choices;
8. whether the same child surfaces can arise from event, reward and shop parents,
   without reading private parent state;
9. the public postconditions for collect, replace and decline, including item
   list/slot changes and any offer-selected flag; and
10. enough overlay ownership/top-surface information to reject an unrelated or
    racing modal without enumerating or interpreting private UI state.

For every emitted item key, owned count, capacity and slot order, this packet
must separately establish actor-public visibility: the fact must be visible to
a normal player or derived solely from such public state through an approved
mapping. A CLR-public member alone does not establish that information boundary.
Private/native instance identities and undisplayed state remain excluded.

If any fact is absent, the corresponding action stays unadvertised. Missing
static evidence is not replaced by a guessed fixture.

## 3. Proposed logical item contract

Everything in this section is **proposed, not frozen**.

### 3.1 Component boundary

The item component owns one item surface at a time. It may observe known
coexisting gold/card reward controls passively, but it never clicks them. It
must receive an exclusive coordinator-owned surface lease before advertising an
item action on a mixed terminal reward surface. While that lease is active, the
reward component must not advertise `proceed` or another action against the same
surface. This prevents two components from racing or treating the same native
click as two actions.

The item component does not require or expose a parent decision ID. An optional
future parent-child token, if required, is a coordinator-owned shared contract
and must remain opaque to item policy features. Item-local resolution releases
the lease; the parent then performs a fresh read and proves its own continuation
or completion.

### 3.2 Bounded public observation

Use a separate logical `decision_kind = "item"`. The proposed ready projection
contains exactly:

| Field | Proposed rule |
| --- | --- |
| `schema_version` | Exact integer `1` within the future item component schema; not a claim about `live_probe_v0`. |
| `status` | `waiting`, `unsupported`, `ready`, or `resolved`. |
| `actionable` | True only for `ready` with a nonempty complete legal-action set. |
| `decision_id` | 64 lowercase hex only for `ready`; null otherwise. |
| `decision_revision` | Nonnegative item-local revision only for `ready`; it advances when any recognized visible control or public inventory fact on the acquired surface changes, including passive coexisting gold/card controls. |
| `screen_kind` | `item_offers`, `potion_replace`, or `unknown`. |
| `surface_ordinal` | Integer `0..999` for a recognized item surface; null for unknown waiting/unsupported. It is allocated from internal run/surface identity but exposes no native instance ID. |
| `offers` | Ordered list of 1..8 exact offer records for `ready`; empty otherwise. |
| `potion_inventory` | Exact public capacity and ordered slots when potion state is required; null for a relic-only surface. |
| `legal_actions` | Exact, duplicate-free list backed one-for-one by mapped, visible, enabled controls. |
| `resolution` | Null except for item-local `resolved`; then one exact resolution record. |

Each offer record is:

```text
offer_slot: int 0..7, contiguous in the frozen public order
kind: "relic" | "potion"
item_id: printable ASCII, length 1..96
owned_count: int 0..999 for this exact public item ID
enabled: bool
supported: bool
can_collect: bool
can_skip: bool
```

`supported` means the reader has every target and reconciliation fact needed for
that offer. It is not a judgment about item value. `can_collect` and `can_skip`
are independent and true only when distinct proven controls exist. A full potion
inventory forces `can_collect = false` on the direct surface; clicking merely to
discover the overflow path is outside the first slice.

Potion inventory is:

```text
capacity: int 1..8
slots: exactly capacity ordered records
  potion_slot: int 0..capacity-1
  item_id: printable ASCII 1..96, or null for publicly empty
```

Eight is a proposed safety ceiling, not a claim about target-game capacity. A
larger or ambiguous inventory is `unsupported` until the contract is reviewed.
The first slice does not expose the complete relic inventory; `owned_count` for
each offered relic is the minimum reconciliation input. Potion slots are exposed
because empty capacity and exact replacement targets are action semantics.

### 3.3 Legal actions and non-equivalences

Proposed action grammar:

| Action | Surface | Exact meaning |
| --- | --- | --- |
| `collect:<offer_slot>` | `item_offers` | Accept this exact offered item. Legal for relic, or potion with a publicly empty slot, only when the mapped control is enabled. |
| `skip:<offer_slot>` | `item_offers` | Decline this exact offer through a distinct proven per-offer skip control. Never synthesized from parent `Proceed`. |
| `replace:<potion_slot>` | `potion_replace` | Give up the exact currently owned potion in this slot and accept the one exact offered potion. |
| `decline_offer` | `potion_replace` | Keep every owned potion slot unchanged and decline the offered potion through a distinct proven child control. |

Replacement of a slot already containing the offered public item ID is
non-legal unless a separately reviewed exact public mutation witness can prove
that replacement. An unchanged slot-ID projection alone cannot reconcile it.

`replace:<slot>` is not discard, potion use, or decline. `decline_offer` is not
replacement with a null slot. `skip:<offer_slot>` is not enclosing reward/event/
shop completion. No generic `proceed`, `close`, `discard`, `use`, `buy`, or
`confirm` action belongs to this component.

On `potion_replace` there is exactly one potion offer, inventory is full, no
direct collect action exists, and every advertised replacement action maps one
exact visible owned slot. `decline_offer` exists only if its separate public
control is established. If the child lacks a safe decline, the omission is
truthful; the item controller may stop without resolving the parent.

### 3.4 Decision identity, replay and races

The proposed decision ID is SHA-256 over a length-prefixed canonical sequence:

```text
"public_item_decision_v1"
screen_kind
surface_ordinal
decision_revision
every ordered offer field
potion capacity and every ordered slot
every ordered legal action and its referenced slot(s)
```

Native object IDs, parent IDs and private state never enter the wire. Internally,
a no-eviction registry of at most 1,000 `(run instance, item surface instance,
first screen kind)` tuples assigns ordinals. A known tuple never receives a new
ordinal after disappearance or A → B → A. A relabeled tuple, exhausted registry,
duplicate control, order ambiguity or unknown top surface fails closed.

Proposed producer bounds are eight reserved dispatches per acquired surface,
three acquired item surfaces and 24 reserved dispatches per process, a
30-second absolute host deadline including health/manifest reads and every item
poll/action, 0.1-second polling, eight offers, eight potion slots, 1,000 retained
surface identities and the existing 4,096-byte response ceiling. These are
safety choices for the current three-destination program, not target-game facts.
The coordinator may lower them during freeze; increasing them requires a new
review. A rejected or stale request before reservation consumes no producer
budget; a post-reservation dispatch fault or lost response retains the consumed
entry. Host attempted, accepted-receipt and reconciled counts are separate.

The applier follows this order:

1. reject an already reserved decision ID or exhausted budget;
2. reread and require the same ready decision ID;
3. require the requested action in `legal_actions`;
4. resolve and revalidate the exact current top surface, offer/control, item ID,
   inventory capacity/slots, visibility and enablement;
5. build the exact pending baseline, then atomically under the session gate
   reserve the decision ID, consume producer budget and install pending facts;
6. dispatch exactly once; and
7. return an accepted bound receipt only if dispatch returns normally, without
   claiming effect reconciliation.

While pending, reads may observe state for reconciliation but expose no legal
action or fresh actionable ID, even if a passive revision, inventory, overlay
or A -> B -> A presentation changes. Pending ends only in correlated item-local
resolution or a fail-closed stop, never by clearing it to mint another decision.

If dispatch throws after reservation, the ID, budget and pending facts remain
intact and the outcome is backend/uncertain. If the response is
lost, malformed, unbound, timed out or interrupted, the host stops and does not
retry, reread to adopt the mutation, or continue a parent. Passive diagnosis
would require a separately approved contract.

### 3.5 Item-local reconciliation

An exact accepted/bound receipt starts reconciliation; it does not finish it.
The host polls only the item decision component within one declared deadline and
requires one of these exact postconditions:

- **Relic collect:** the offered relic's public owned count increases by exactly
  one, and the same offer is publicly resolved by the established offer-local
  predicate.
- **Potion collect:** capacity is unchanged; exactly one previously empty slot
  becomes the offered potion ID; slot count/order and every other slot,
  including other empty slots, are unchanged; and the offer-local resolved
  predicate passes.
- **Direct skip:** observed capacity, slot count/order, every potion slot and
  offered-item owned counts remain unchanged, and the exact offer-local skipped
  predicate passes.
- **Potion replace:** capacity and slot count are unchanged; the requested slot
  changes from its exact prior potion ID to the offered potion ID; every other
  slot is unchanged; and the child resolution predicate passes.
- **Potion decline:** capacity, slot count/order and every potion slot are
  byte-for-byte equal to the before projection, and the child decline predicate
  passes.

HP, max HP, gold and deck count are not asserted unchanged because repository
evidence does not establish item acquisition side effects. Conversely, screen
disappearance alone never satisfies a postcondition. Extra item/inventory
changes, reordered slots, another modal, a changed run/surface, a repeated ID,
or timeout is a reconciliation failure and a no-retry stop.

After a successful postcondition the component may emit item-local `resolved`
with:

```text
kind: "collected" | "skipped" | "replaced" | "declined"
offer_kind: "relic" | "potion"
item_id: exact offered public ID
replaced_potion_slot: int or null
replaced_potion_id: exact prior public ID or null
```

This record is incomplete until coordinator freeze defines exact correlation
back to the accepted decision/action, offer slot and acquired surface/lease
lifetime, together with the required before/after evidence. A null ready
`decision_id` in `resolved` is not that correlation. The host must not accept an
uncorrelated terminal record or adopt another action's result; exact field
spelling and canonical validation are shared blocking decisions.

Once that correlation and the postcondition are validated, the record proves
only the named item-local transition. It contains no
`parent_complete`, `room_complete`, `payment_complete`, `reward_complete`, map,
floor, or run field. A fresh parent read owns all subsequent claims.

### 3.6 Action accounting and handoff

Count one native mutation under exactly one component:

- a parent event choice that opens an item child remains one event/room action;
- an item collect/skip/replace/decline is one item action;
- a reward-to-item handoff is metadata and costs no action;
- a shop purchase that atomically debits and grants an item belongs to the shop
  transaction lane, not the item lane;
- if a shop purchase opens a genuine item child, the accepted purchase is one
  shop action and a later child choice is one item action; neither component may
  duplicate the other's count; and
- releasing an item lease or rereading a parent costs no action.

The host increments attempted once on entry into an action exchange, accepted
only after exact accepted-receipt validation, and reconciled only after the
correlated item postcondition. Receipt acceptance does not increment attempted
again. A lost receipt leaves acceptance unproved even when the producer consumed
a reservation; later state cannot retroactively establish receipt acceptance.
Parent success accounting remains absent until the parent validates it.

Failure output is also a shared freeze decision. Partial-prefix counters may be
emitted only if a versioned successor expressly admits them; otherwise emit only
the selected fixed failure contract and retain no partial result. This proposal
does not add counters or fields to existing accepted run/diagnostic schemas.

### 3.7 Mixed and unknown surfaces

- A mixed terminal reward screen is item-actionable only after the combined
  classifier recognizes every visible reward as an existing gold/card family or
  an established relic/potion family, preserves the frozen order, and the router
  grants an exclusive item lease. Unknown rewards make the item projection
  `unsupported`; they are never silently ignored.
- Known gold/card controls are passive context for item binding. The item
  component does not expose or click them.
- A recognized item child may sit above an event/reward/shop parent. Only the
  visible top item surface is controlled; the component does not infer the
  underlying parent or its completion.
- An unrelated top overlay returns non-actionable `waiting` when no item surface
  has been acquired. If it replaces or covers an acquired surface, the pending
  item state fails closed as `unsupported`/reconciliation failure.
- Simultaneous ambiguous item surfaces, unknown visible controls, duplicate
  offers/models, inconsistent players, disabled/loading controls, malformed
  inventory, or a full potion inventory without a recognized replacement child
  are non-actionable.
- A new overlay appearing between GET and POST is caught by immediate
  revalidation and returns stale without a click or budget consumption.

The coordinator must freeze arbitration before a mixed screen is enabled. Until
then, the safest implementable first slice is a recognized top-level item-only
surface; current reward/room controls remain unchanged and fail closed.

## 4. Producer, consumer and version impact

### 4.1 Proposed future item-owner files

The future item producer may own these new files:

- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicItemDecision.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicItemAction.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicItemDecisionReader.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicItemActionApplier.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicItemInteractionSession.cs`
- `bridge/Sts2AgentBridge/tests/Sts2AgentBridge.Tests/Public/ItemInteractionTestSuite.cs`
- `bridge/Sts2AgentBridge/tools/apply_item_live.py`
- `bridge/Sts2AgentBridge/tools/apply_item_live_fixtures.py`
- `tests/backends/live/test_apply_item_live_fixtures.py`

The producer must not edit them until Sections 2.4 and 3 are independently
reviewed and frozen.

### 4.2 Coordinator-owned shared files

A separate reviewed integration packet owns any changes to:

- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Sts2AgentBridge.csproj`
- `Adapters/Bootstrap/BridgeBootstrap.cs`
- `Core/Protocol/CanonicalProbeEncoder.cs`
- `Core/Protocol/ProbeRoutes.cs`
- `Core/Transport/ProbeRequestParser.cs`
- `Core/Transport/ProbeRequestProcessor.cs`
- `Core/Transport/BoundedLoopbackServer.cs`
- the contract vectors and `contracts/*/forbidden_surface.json`
- contract, transport, hosting, public aggregate and verifier test suites
- `tools/Sts2AgentBridge.Verifier/*`
- `tools/probe_live.py` and its fixtures
- package manifest/version, build/reproducibility pins, README and shared status/
  decision/acceptance documents.

The route and surface policy are exact closed sets today. The preferred outcome
is a successor protocol/bridge version with separate item decision/action
transport while preserving every `live_probe_v0` byte and bridge `0.8.0`
artifact. Reusing the existing reward route would require changing its exact DTO,
host parser, vectors and semantics and still would not provide a clean event/shop
child boundary. It is therefore not recommended. The coordinator may select a
different versioning mechanism after reconciling all three MR proposals.

Receipt vocabulary is also shared. If the successor retains the existing
`mutation_state = "applied"` envelope, documentation and tests must state that it
is a receipt claim, not effect reconciliation. Changing that word to `submitted`
would be clearer but is a coordinator-owned successor-contract decision.

### 4.3 Later consumers, read-only in this packet

- The reward lane must pause/suppress `proceed` while an unselected supported
  item owns a mixed reward surface, then freshly revalidate after item resolution.
- The event lane may open and resume from an item child but owns event step,
  consequence and completion. It consumes item-local results without redefining
  item actions.
- The shop lane owns inventory pricing, availability, debit, purchase identity,
  payment/acquisition ordering and atomic-purchase behavior. It hands off only a
  genuine post-purchase item child.
- Run integration may expose item counts only after independent item acceptance
  and an explicit versioned output-contract freeze. Existing accepted run and
  diagnostic schemas remain exact. Never count a handoff or native mutation twice.
- `headless_v0`, its encoding, candidates, trajectories, datasets and policies
  remain unchanged. A later headless successor requires separately sourced game
  semantics and a new conformance decision.

## 5. Synthetic acceptance specification

This is a test specification, not passing runtime, fixture, live or differential
evidence. Target-API fixtures may be authored only after the exact API closure is
accepted; until then, logical DTO/session fixtures can test no game-specific
member.

### 5.1 Positive and passive-read cases

| ID | Synthetic setup | Required result |
| --- | --- | --- |
| `ITEM-PASSIVE-01` | Repeated GET of one unchanged recognized item surface | Byte-identical ready projection and decision ID; zero control calls; zero reservations/budget; no parent state read or completion claim. |
| `ITEM-PASSIVE-02` | Recognized mixed gold/card/relic/potion terminal surface under an item lease | Item projection includes only item offers but identity binds the complete recognized surface generation; no gold/card/proceed control is touched. |
| `ITEM-COLLECT-RELIC-01` | Enabled relic offer, owned count `k` | One advertised collect, one dispatch, accepted bound receipt, later owned count `k+1` plus exact offer resolution; item-local `collected`; parent unresolved. |
| `ITEM-COLLECT-POTION-01` | Enabled potion offer, capacity 3, slots `[A,null,B]` | One dispatch; after `[A,offered,B]`; all other slots exact; item-local `collected`; parent unresolved. |
| `ITEM-SKIP-01` | Exact visible enabled per-offer skip control | `skip:<offer>` advertised; one dispatch; inventory/counts unchanged and exact skipped predicate; no parent Proceed. |
| `ITEM-REPLACE-01` | Full `[A,B,C]`, offered `D`, recognized replacement child | `replace:1` changes only slot 1 to `D`; resolution records prior `B`; no discard/use action and no parent completion. |
| `ITEM-DECLINE-01` | Same full child with distinct decline control | `decline_offer` leaves `[A,B,C]` exact and resolves only the offered child; it is never represented as `replace:null`. |
| `ITEM-HANDOFF-01` | Accepted event action opens item child; item later resolves | Event action count 1, item action count 1, handoff count 0; event/room still requires a fresh independent completion check. |
| `ITEM-HANDOFF-02` | Shop action atomically debits and grants | Shop owns one action; item owns zero. A genuine later replacement child instead yields one shop plus one item action. |

### 5.2 Malformed, bounds and hidden-information cases

| ID | Synthetic setup | Required result |
| --- | --- | --- |
| `ITEM-MALFORMED-01` | Duplicate/missing/extra JSON keys, non-ASCII, duplicate keys, non-finite or bool-as-int values | Strict parser mismatch; no POST, retry or partial result. |
| `ITEM-MALFORMED-02` | Empty/overlong item ID, unknown kind, duplicate offer slot, noncontiguous slot/order, impossible flags | Producer fails closed or consumer rejects; no legal action. |
| `ITEM-MALFORMED-03` | Capacity/slot length mismatch, duplicate potion slots, null occupied replacement target, inventory required but absent | `unsupported` or parser mismatch; no action. |
| `ITEM-BOUND-01` | 9 offers, 9 potion slots, fourth acquired surface, 25th process action, 1,001st new identity, action outside grammar, response over 4,096 bytes | Exact bounded failure; no truncation, hidden candidate or click. |
| `ITEM-UNKNOWN-01` | Unknown reward/control mixed with recognized items | Whole acquired item surface is `unsupported`; known items are not actioned around it. |
| `ITEM-UNKNOWN-02` | Unknown top overlay, ambiguous simultaneous item surfaces, relabeled known surface | Non-actionable and no private inspection fallback. |
| `ITEM-INFO-01` | Fixture supplies private reward outcome, RNG, shop price internals or event effect | Projection and decision identity are unchanged; forbidden fields never enter policy or reconciliation. |
| `ITEM-FULL-01` | Full potion inventory but no established replacement child/API | Direct collect is absent; no implicit replace/discard/decline; typed unsupported stop. |
| `ITEM-NOSKIP-01` | Parent Proceed exists but no per-offer skip | No item skip/decline legal action. Parent ownership is unchanged. |

### 5.3 Stale, reorder, overlay and immediate-revalidation cases

| ID | Synthetic setup | Required result |
| --- | --- | --- |
| `ITEM-STALE-01` | Offer list reordered, inserted or removed between GET and POST | New decision ID or target mismatch; stale rejection; zero click and zero budget. |
| `ITEM-STALE-02` | Offered item ID/model changes in place | Immediate reread/reference check rejects stale; old item never collected. |
| `ITEM-STALE-03` | Potion capacity, empty slot or any owned slot changes before POST | Stale rejection; no replacement/collect and no budget. |
| `ITEM-STALE-04` | Target becomes hidden/disabled or maps to a different control | Stale rejection; zero signal/click. |
| `ITEM-OVERLAY-01` | Map, card selection or unrelated modal becomes top after GET | Immediate revalidation rejects stale; underlying item control is never clicked. |
| `ITEM-OVERLAY-02` | Recognized child disappears before POST or A → B → A occurs | Old ID remains non-applicable; no new ordinal for the same registered surface. |
| `ITEM-OVERLAY-03` | Overlay changes after accepted dispatch but before reconciliation | Stop as reconciliation failure/unsupported; do not infer success from disappearance. |
| `ITEM-MIXED-01` | Reward and item routes are both queried on one mixed surface | Router grants at most one actionable lease; no simultaneous legal actions and no parent Proceed while item owns it. |

### 5.4 Receipt, uncertainty, replay and cleanup cases

| ID | Synthetic setup | Required result |
| --- | --- | --- |
| `ITEM-REJECT-01` | Canonical `stale_decision`, `invalid_action`, `already_applied`, or `action_limit_reached` | Exact rejected receipt, mutation none, no reconciliation/parent continuation, no retry. |
| `ITEM-DUPLICATE-01` | Same accepted decision POSTed twice by the synthetic harness | First dispatches once; second is `already_applied`; producer reservations and accepted/item totals remain one. If the harness enters two host exchanges, attempted is two; production never retries. |
| `ITEM-REPLAY-01` | Accepted surface disappears and later returns unchanged | Registry and accepted-ID history prevent replay; no second click or ordinal reset. |
| `ITEM-REPLAY-02` | A → B → A surfaces or same numeric pair with conflicting kind | Original A remains reserved; conflict fails closed; capacity exhaustion cannot mint a fresh identity. |
| `ITEM-UNCERTAIN-01` | Request fully sent, receipt lost/timeout/connection reset | Attempted may be 1; accepted/reconciled remain unproved; stop with no GET, retry, adoption or parent continuation. |
| `ITEM-UNCERTAIN-02` | Malformed/unbound accepted receipt | Receipt rejected; actual effect unknown; no retry or state-based retroactive acceptance. |
| `ITEM-RECONCILE-01` | Accepted receipt but item count/slots unchanged, overchanged, reordered, or wrong item acquired | Reconciliation failure; accepted 1, reconciled 0; no item/parent success. |
| `ITEM-RECONCILE-02` | Accepted receipt then only child disappearance | Waiting until bounded deadline, then failure; disappearance is not resolution. |
| `ITEM-BUDGET-01` | Producer reserved-dispatch/surface/process ceiling reached, including post-reservation faults | Further actions reject before click. Pre-reservation stale/rejected requests consume no budget; consumed slots survive faults/lost receipts and do not imply host receipt acceptance. |
| `ITEM-DEADLINE-01` | Resolution arrives one millisecond before the 30-second deadline, and separately at/after it | Before-deadline case may pass exact reconciliation; boundary/late case stops once with timeout and no retry or parent continuation. |
| `ITEM-CANCEL-01` | Cancellation before send, during send/receive, and after accepted receipt | Stop once; close every socket; zero credential and reachable mutable request/response buffers; no retry or later parent action. |
| `ITEM-CLEANUP-01` | Close/cleanup callback fails after another outcome | Fixed cleanup/internal failure takes declared precedence; no arbitrary exception text, raw body, IDs or player/item history emitted. |
| `ITEM-ACCOUNT-01` | Parent and item accounting joined after item reconciliation failure | Internal attempted/accepted/reconciled counts remain distinct and total equals component sums; handoff counts zero. Emit partial-prefix fields only under an explicit successor output contract; otherwise fixed failure only, with no partial result. |

### 5.5 Review-required correlation and race cases

| ID | Synthetic setup | Required result |
| --- | --- | --- |
| `ITEM-PENDING-01` | Reentrant read during dispatch, followed by mutation and a thrown dispatch exception | Pending baseline, reservation and producer-budget entry exist before dispatch. The read advertises no action; all three remain after the exception; no host accepted receipt is invented. |
| `ITEM-REPLAY-03` | Pending action followed by passive inventory/overlay revision A -> B -> A | No fresh actionable ID or second dispatch until the original pending action is correlated and resolved; contradiction fails closed without clearing reservation. |
| `ITEM-INVENTORY-01` | Collect with multiple empty slots; separately change a second empty slot, capacity, length or order during collect/skip/decline | Exactly one previously empty slot may fill on collect; every required unchanged field remains exact. Every extra change rejects reconciliation. |
| `ITEM-SAMEID-01` | Offered potion ID equals the occupied replacement slot's public ID | Replacement is non-legal without a separately accepted public mutation witness; unchanged IDs alone never prove replacement. |
| `ITEM-CORRELATE-01` | Correct item outcome paired with another decision/action, offer slot, surface or lease lifetime | Host rejects the terminal result; no item or parent success, retry or result adoption. |
| `ITEM-INFO-02` | Change private/native model-instance identity or undisplayed sibling state while keeping all admitted visible facts equal | Public projection and decision hash remain equal; no private identity or hidden fact becomes a field, policy feature or substitute reconciliation witness. |

## 6. Dependency-ordered implementation plan

1. **`ITEM-STATIC-00` — target API closure.** Produce a sanitized exact
   type/member/control/postcondition report answering every Section 2.4 fact.
   Independent reviewer checks the pinned build binding, public-information
   boundary and absence of executable/live discovery. Coordinator accepts an
   exact report hash or keeps affected actions excluded.

2. **`ITEM-CONTRACT-01` — shared freeze.** Reconcile this proposal with shop and
   event proposals. Freeze logical fields, action grammar, item-local resolution,
   mixed-surface arbitration, cross-component reservation/accounting, receipt
   vocabulary, route/version and target limits. Add no implementation before the
   exact freeze is recorded.

3. **`ITEM-CORE-02` — DTO/identity/encoder.** Add the item-owned core records and
   exhaustive pure contract tests. The coordinator integrates route, parser,
   processor, bootstrap, canonical encoder, vectors and verifier allowlist in a
   separate commit. Negative controls must show `live_probe_v0`/0.8.0 remains
   byte-identical and the old surface policy rejects the new types/routes.

4. **`ITEM-READ-03` — passive producer.** Implement only bounded read projection,
   stable surface identity, mixed/unknown fail-closed rules and no controls.
   Review exact target members and prove repeated reads are passive.

5. **`ITEM-DIRECT-04` — smallest useful mutation slice.** Add direct relic and
   non-full potion collect only, with immediate revalidation, reservation,
   no-retry semantics and inventory reconciliation. Enable per-offer skip only if
   `ITEM-STATIC-00` proves it. Do not add replacement by clicking through overflow.

6. **`ITEM-OVERFLOW-05` — explicit replacement/decline.** After a separate static
   and fixture review of the full-inventory child, add exact slot replacement and
   distinct decline. Run the entire Section 5 matrix, including direct-slice
   negative controls.

7. **`ITEM-HOST-06` — independent actual-client gate.** Implement the strict
   Python item client over literal fake transport. Exercise production entry
   points, exact request bytes, all receipts, uncertainty, deadlines, action
   accounting, cancellation and cleanup. It must not substitute a controller
   result or reproduce producer orchestration.

8. **`ITEM-JOIN-07` — parent consumers.** Only after independent item acceptance,
   let reward/event/shop owners consume it under the frozen lease/handoff contract.
   Each parent retains its own completion and financial/effect reconciliation.
   Add aggregate gates proving no double count and no continuation after item
   uncertainty.

9. **`ITEM-REVIEW-08` — high-risk aggregate review.** Read the complete joined
   diff, source closure, vectors, artifact/version pins and negative controls.
   Run focused C#/Python/transport/surface/reproducibility tests and the full
   repository suite on the integrated source. Fixture success remains
   `bridge_fixture` only.

10. **`ITEM-LIVE-09` — coordinator-only future campaign.** Requires a fresh exact
    artifact-bound authorization, the precise screen below, one invocation, fixed
    retained aggregate, immediate stop on uncertainty and normal scoped cleanup.
    Live item resolution still does not certify its parent.

Rollback before live integration is removal of the successor-only route/component
and restoration of its exact contract/policy/package pins. Existing 0.8.0 files,
vectors and defaults remain the negative-control baseline throughout.

## 7. Precise future live entry state

The first bounded live gate should test the smallest parent-independent potion
slice already motivated by checked-in evidence:

- dedicated **Profile 3**, **Ironclad**, **Ascension 0**;
- a fresh, visibly topmost **potion-loot offer** with its offered potion visible;
- no item collect, skip, replacement, close or parent continuation action has
  been taken;
- at least one potion inventory slot is visibly empty, so replacement and
  decline are not part of this gate;
- no map, shop, treasure, card-reward, replacement/confirmation screen or other
  modal is above the offer; and
- the enclosing event/reward/room state is not used as input or claimed as
  complete.

The user may prepare that exact visible state only inside a later authorized
campaign. The coordinator verifies it before invoking the item client once. The
client may perform one direct potion collect and prove only the exact empty-slot
inventory transition. It then stops; it does not resume the event, proceed the
reward, select the map, explore a replacement screen, or retry an uncertain
action. If the surface is not the statically accepted type or inventory is full,
the gate is `unobserved`/unsupported rather than widened.

A later relic gate requires a separate fresh untouched public relic offer. A
later overflow gate requires an exact full potion inventory and untouched
replacement child with the offered potion plus all owned slots and any distinct
decline control visible. Neither should be combined with the first campaign.

## 8. Exclusions and current disposition

This proposal does not include potion use/discard, treasure-room entry, card-
reward redesign, generic modal refactoring, event lifecycle/effects/completion,
shop pricing/payment/removal, boss/act transitions, automatic phase detection,
uncertain-action recovery, retained live data, headless item rules, training
features, or a full-run controller.

The source audit supports the logical boundary and synthetic specification. It
does **not** establish the target item APIs needed to implement even the first
control safely. `ITEM-STATIC-00` and the coordinator's shared contract/version
freeze are hard gates, not documentation follow-ups. Until both pass, all relic
and potion controls remain disabled and the current bridge behavior remains the
only accepted behavior.
