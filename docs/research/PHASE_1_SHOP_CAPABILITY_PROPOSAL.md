# Phase 1 shop capability proposal

- **Task:** `MR-SHOP-01`
- **Date:** 2026-09-05
- **Baseline:** `68c8b50eed05d5442c66cc55f9ec9cf0513c7009`
- **Current bridge:** `live_probe_v0`, bridge `0.8.0`, milestone `R0i`
- **Evidence level:** repository source and checked-in sanitized static research only
- **Status:** implementation-ready design input; every new contract below is
  **proposed and unfrozen**

This document owns merchant transactions and the proposed shop-to-host handoff.
It does not define generic relic or potion collection, potion replacement, or
overflow-child controls; those belong to `MR-LOOT-02`. It does not authorize a
bridge build, install, game launch, live read, live mutation, schema change, or
production implementation. A synthetic matrix below is an acceptance
specification, not passing fixture, runtime, live, or differential evidence.

## 1. Outcome and recommended first slice

The smallest useful shop slice should be:

1. passively observe one already-open ordinary merchant screen;
2. expose every bounded visible stock slot with public slot identity, kind,
   public model key where established, displayed price, affordability, native
   enabled state, and bridge support state;
3. permit a snapshot-bound purchase only for an ordinary card whose acquisition
   can be reconciled from the already-used public deck/card surface;
4. permit the explicit visible leave control; and
5. return to the host only after the same-shop transaction or leave action is
   reconciled.

Relic and potion stock remains visible but not legal in the first slice. Card
removal is represented in the proposed state machine but remains non-legal
until a bounded target-build static member audit establishes open/select/
confirm/cancel behavior. This is still useful: it lets a controller inspect a
shop, buy an affordable card, decline everything else, and leave without
silently treating unsupported stock as absent.

The first slice deliberately does not assume that debit and acquisition are one
atomic game API. After an accepted purchase dispatch, the shop producer enters
one pending transaction and advertises no further mutation until it observes
both the exact debit and the exact acquisition. One-sided or contradictory
effects stop fail-closed and never authorize a retry.

## 2. Evidence classification

### 2.1 Current repository facts

- The map reader already classifies `MapPointType.Shop` as public destination
  kind `shop`; it does not enter or control a shop
  ([`PinnedPublicMapDecisionReader.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicMapDecisionReader.cs)).
- The current room reader recognizes only visible rest-site and event rooms.
  Every nested overlay makes that boundary unsupported, and shops have no
  reader, action applier, route, DTO, encoder, host client, or provider
  ([`PinnedPublicRoomDecisionReader.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomDecisionReader.cs),
  [`ProbeRoutes.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/ProbeRoutes.cs)).
- The run host maps only `rest_site` and `ancient` destinations into the room
  client. Shop and treasure destinations stop as typed unsupported boundaries
  ([`apply_run_live.py`](../../bridge/Sts2AgentBridge/tools/apply_run_live.py)).
- `live_probe_v0` currently registers exactly health, manifest, screen,
  combat, reward, map, and room routes. Its manifest identifies bridge `0.8.0`;
  adding shop routes is therefore a public artifact and version change, not an
  invisible implementation detail
  ([`ProbeRoutes.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/ProbeRoutes.cs),
  [`manifest_compatible.json`](../../bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors/manifest_compatible.json)).
- Existing action families compute a decision hash from the complete public
  candidate projection, resolve a requested candidate again, re-read the
  decision immediately before dispatch, reserve the decision before clicking,
  and return a bounded receipt. Room reservations survive a changed foreground
  projection and reject duplicate application
  ([`PublicRoomDecision.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicRoomDecision.cs),
  [`PinnedPublicRoomActionApplier.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomActionApplier.cs)).
- The reward producer already projects public player gold and deck count, uses
  `CardModel.Id.Entry` for offered cards, counts copies in the player's deck,
  and does not call a card acquisition reconciled until deck count and the
  chosen model's copy count each increase by one
  ([`PublicRewardDecision.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicRewardDecision.cs),
  [`PinnedPublicRewardDecisionReader.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardDecisionReader.cs)).
- Existing reward handling separates an accepted dispatch receipt from later
  mutation reconciliation. `D49` and the host diagnostic separately count
  attempted exchanges, accepted/bound receipts, and reconciled effects
  ([`DECISIONS.md`, D49](../../DECISIONS.md#d49-separate-reward-attempts-receipt-acceptance-and-reconciliation)).
- `D47` requires same-room context and accepted-action evidence for completion;
  foreground disappearance alone is not completion. `D50` preserves one
  bounded host transport while keeping phase semantics separate
  ([`DECISIONS.md`, D47](../../DECISIONS.md#d47-separate-room-identity-from-foreground-and-completion-evidence),
  [`DECISIONS.md`, D50](../../DECISIONS.md#d50-centralize-bounded-host-transport-without-merging-phase-semantics)).
- The latest event campaign observed a potion-loot overlay after one accepted
  event receipt, but the retained aggregate did not identify its exact cause or
  establish collection/skip semantics. It supplies no shop or generic-item
  control evidence
  ([`PHASE_1_ACTOR_READY_ACCEPTANCE.md`](PHASE_1_ACTOR_READY_ACCEPTANCE.md)).

### 2.2 Checked-in sanitized static reference evidence

- At exact upstream pin `55e0648`, STS2MCP declares merchant state and
  purchase/removal support. That pin compiled unchanged against the exact
  target-build arm64 assemblies; the compatibility update specifically touched
  per-player merchant inventory access. This proves ordinary member/signature
  compatibility for the compiled upstream source, not project-bridge runtime
  behavior, public safety, passivity, ordering, or transaction correctness
  ([`PHASE_1_LIVE_BRIDGE_DOSSIERS.md`](PHASE_1_LIVE_BRIDGE_DOSSIERS.md),
  [`PHASE_1_STS2MCP_COMPILE_PROBE.md`](PHASE_1_STS2MCP_COMPILE_PROBE.md)).
- The same upstream reference can open merchant inventory while nominally
  reading state. It has mutable list indices and no decision ID, expected-state
  precondition, idempotency result cache, or ambiguous-commit recovery. Those
  behaviors are negative design evidence: this proposal must not copy its
  read/action semantics wholesale.
- The pinned netcan source statically exposes shop card/relic/potion purchase,
  purge opening, and leave, but no explicit post-purge selection. It is an older
  Windows-target reference and is not target-build runtime evidence.
- The STS1 CommunicationMod reference has generic choice/confirm/cancel/leave
  precedent and explicitly reports full-potion-belt failures without feedback.
  It is not an STS2 API or semantic authority.

### 2.3 Precise unknowns and required static facts

No checked-in project source establishes the following facts for the pinned
game. They must be answered by a separately reviewed, build-only/static member
packet before production code is assigned. If any cannot be established, the
corresponding candidate stays visible-but-unsupported or the whole projection
fails closed.

1. The exact ordinary merchant node/screen type, how to prove it is the visible
   top interactive surface, and the non-mutating accessor for an already-open
   inventory. A read must never call an open/populate method.
2. The exact ordered visible stock controls and their card/relic/potion model,
   displayed price, sold/available state, native enabled state, and click
   members. It must be possible to distinguish a visible slot from a private
   item instance.
3. Whether stock order can change after opening or purchase, whether sold stock
   is removed, retained disabled, or replaced, and whether two visible slots
   may carry the same public model key and price.
4. The exact public player gold accessor at the merchant and the timing/order of
   gold debit relative to card/relic/potion acquisition.
5. The exact relic ownership and potion-belt public surfaces needed to reconcile
   acquisition, including potion capacity and the full-belt behavior. These are
   shared with `MR-LOOT-02` and must not be invented here.
6. The exact card-removal service availability, displayed price, open control,
   selectable-card controls or paging, selected-card public identity, explicit
   confirm/cancel controls, and whether selection ever commits immediately.
7. The exact leave control and authoritative post-leave evidence. In
   particular, whether accepted leave leads directly to an open travel-enabled
   map on the pinned build.
8. Whether purchase can open any child screen or item-overflow decision before
   both payment and acquisition are externally observable.

The checked-in research links exact upstream files that may be audited in a
future approved source packet. This task did not fetch, clone, rebuild, or read
the installed game or those remote repositories.

## 3. Proposed public shop contract (unfrozen)

### 3.1 Separate route and lifecycle

Use a shop-specific decision/action family rather than adding merchant
semantics to `PublicRoomDecision`. Proposed endpoints are:

```text
GET  /probe/v0/public/shop-decision
POST /probe/v0/public/shop-action
```

The shared transport, authentication, limits, game-thread dispatch, canonical
response envelope, and error vocabulary remain unchanged. Shop-specific state,
identity, legality, reservation, pending reconciliation, and completion stay in
one shop producer/session. The existing room and reward DTOs remain exact.

Adding these endpoints and response bodies should keep protocol name
`live_probe_v0` only if coordinator review confirms additive compatibility, but
it requires at least a bridge minor-version bump and new exact vectors. The
working recommendation is a future `0.9.0`; this proposal does **not** change
the current `0.8.0` artifact or declare that version accepted.

### 3.2 Decision shape

Illustrative field names below specify meaning, not frozen JSON spelling:

```text
PublicShopDecisionSnapshot
  status: waiting | unsupported | ready | complete
  decision_id: canonical SHA-256 for ready, otherwise absent
  screen_kind: shop | unknown
  phase: browse | removal_select | removal_confirm | child_waiting |
         transaction_waiting | unsupported | complete | unknown
  shop_ordinal: bounded process-local public ordinal
  decision_revision: nonnegative bounded revision within this shop incarnation
  player: { gold, deck_count, potion_count?, potion_capacity? }
  candidates: ordered PublicShopCandidate[]
  legal_actions: ordered action-id list
```

`potion_count` and `potion_capacity` are included only after the coordinator
freezes a shared public item-capacity shape with `MR-LOOT-02`; absence must not
mean zero. They are not required by the first slice.

Each candidate is proposed as:

```text
PublicShopCandidate
  candidate_index: contiguous index in this exact projection
  action_id: bounded semantic action bound to this projection
  kind: purchase_card | purchase_relic | purchase_potion |
        open_card_removal | remove_card | confirm_card_removal |
        cancel_card_removal | leave
  public_slot_id: visible presentation slot, not an engine instance ID
  item_key: public model key when applicable, otherwise absent
  price: displayed nonnegative integer when the action charges gold,
         otherwise absent
  affordable: price is present and player.gold >= price
  enabled: the exact visible native control is enabled
  supported: bridge can reconcile this kind under the frozen slice
  selected: only for a visible removal-card candidate
```

`legal_actions` is authoritative. For a purchase candidate, `affordable` is a
transparent arithmetic fact, not legality: legal also requires visible/native
enabled state, supported kind, no foreground conflict, no pending mutation,
and all item-specific preconditions. A disabled or unsupported visible item
remains in `candidates` so policy code cannot mistake omission for absence.

Proposed action IDs encode the semantic category and `public_slot_id`, for
example `buy:card:0`, `removal:open`, `remove:visible:3`, `removal:confirm`,
`removal:cancel`, and `leave`. Exact grammar and lengths are coordinator-owned.
The action request also carries the canonical `decision_id`; it never accepts a
bare list index or private object/instance ID.

### 3.3 Public slot and duplicate identity

A stock slot is the visible presentation position (`card:0`, `card:1`,
`relic:0`, `potion:0`, `service:removal`, `leave`), scoped by
`shop_ordinal` and the complete decision hash. `item_key` describes what is in
that slot but is not unique. Two copies of the same card or potion therefore
remain two candidates even if model key and price are equal.

The producer may retain a numeric game-object identity privately only to bind
the same run/shop/control during immediate revalidation; that value never
enters the response, decision-hash input, log, host result, model input, or
persisted artifact. On apply, it resolves the current visible slot again and
requires the expected kind, public model key, price, enabled state, and control
surface. Reordering, sale/removal, replacement, or price changes make the old
decision stale before reservation. A model key alone can never retarget a
duplicate.

The decision hash covers phase, shop ordinal, revision, public player fields,
every candidate field in order, and legal actions in order. Changing stock,
gold, native availability, affordability, selection, or foreground phase must
change the decision or yield waiting/unsupported. Stable identical re-reads
produce the same hash.

### 3.4 Candidate legality by phase

| Phase | Candidate | Proposed legality |
| --- | --- | --- |
| `browse` | affordable direct card purchase | legal in first slice when enabled |
| `browse` | relic purchase | visible, unsupported in first slice |
| `browse` | potion purchase | visible, unsupported until shared item-capacity/child contract freezes |
| `browse` | removal service open | visible, unsupported in first slice; later legal only when exact price/enabled behavior is established |
| `browse` | leave | legal in first slice when the exact visible leave control is enabled |
| `removal_select` | visible deck card | later legal; duplicate cards use visible slot plus model key |
| `removal_select` | cancel | later legal only when a visible native cancel exists |
| `removal_confirm` | confirm | later legal only when a selected card and visible native confirm exist and exact total price is affordable |
| `removal_confirm` | cancel | later legal only when a visible native cancel exists |
| `transaction_waiting` / `child_waiting` | any | none |

The producer fails closed rather than synthesizing `skip`, `cancel`, `confirm`,
or leave from screen disappearance, keyboard conventions, or upstream prose.

### 3.5 Apply, receipt, reservation, and revalidation

Use the established bounded outcomes: `accepted`, `stale_decision`,
`invalid_action`, `already_applied`, `action_limit_reached`, and
`backend_fault`. An accepted response means one exact current control was
reserved and dispatched; it is not proof of payment, acquisition, removal, or
shop completion.

Apply order is mandatory:

1. reject malformed request or an already-reserved decision;
2. obtain a fresh shop projection and require exact decision ID;
3. resolve the requested public slot and verify it is advertised and legal;
4. resolve the native control and all public item/price/enabled facts;
5. immediately re-read the top surface and full projection;
6. require same run/shop incarnation, phase, decision ID, slot facts, and no
   overlay/map/travel conflict;
7. reserve the decision and charge exactly one shop action-budget entry;
8. dispatch once; and
9. record a pending semantic mutation before publishing another ready state.

Stale and invalid requests do not consume the accepted-action budget. Once
reserved, a duplicate request is `already_applied` even if the screen has since
changed. Exceptions after reservation are uncertain and never release the
reservation or permit automatic retry.

The first implementation should cap accepted shop actions independently. A
proposed cap is 12 per process and 12 candidates per decision, with exact body
size still bounded by `LiveProbeLimits.MaximumResponseBodyBytes`. These values
are design bounds, not target-game inventory claims. The static packet must
show that an ordinary supported shop fits; a valid larger surface is
`unsupported`, never truncated. The producer also bounds shop incarnations,
revisions, retained reservation keys, model-key length, and removal-card visible
slots. Exact constants require contract review and vector-size proof.

### 3.6 Purchase reconciliation without atomicity assumptions

Before a direct card purchase, retain only the minimum private pending facts:
same shop/control binding, public slot, card key, displayed price, player gold,
deck count, and copies of that card. Do not assume which effect happens first.

A direct card purchase reconciles only when all of these are observed together:

- gold is exactly `before_gold - displayed_price`;
- deck count is exactly `before_deck_count + 1`;
- the selected card key's copy count is exactly `before_copies + 1`;
- unrelated public player invariants selected by contract review have not
  contradicted the purchase; and
- the same sold slot is absent/disabled or the shop projection otherwise has a
  coherent next revision.

While only debit or only acquisition is visible, return `waiting` with zero
legal actions. If the other half appears before the fixed host deadline,
reconcile once. If the deadline expires, the surface changes incompatibly, the
debit is wrong, the wrong item appears, or both sides cannot be correlated,
stop with a fixed uncertainty/reconciliation failure. Never click again, refund,
infer rollback, or call the accepted receipt an applied purchase.

Relic purchase later needs an independently established ownership delta for the
specific public relic key. Potion purchase later consumes the frozen generic
item acquisition/overflow contract from `MR-LOOT-02`. If a purchase opens an
item/overflow child, the shop transaction remains pending across the handoff.
Child resolution alone cannot prove payment or parent completion.

### 3.7 Card-removal lifecycle (later slice)

The proposed later lifecycle is intentionally tolerant of multiple UI stages
but not of ambiguous semantics:

```text
browse --open_card_removal--> removal_select
removal_select --remove_card--> removal_confirm   (only if target has confirm)
removal_select --cancel_card_removal--> browse
removal_confirm --confirm_card_removal--> transaction_waiting --> browse
removal_confirm --cancel_card_removal--> removal_select or browse
```

Opening reconciles only when the exact removal child is visibly interactive and
gold/deck are unchanged. Selection binds the exact visible deck slot plus public
card key. Confirmation reconciles only when gold decreases by the displayed
service price, deck count decreases by one, and the selected key's copy count
decreases by one. Cancel reconciles only when the advertised child closes or
returns to its defined parent stage with gold/deck unchanged.

If the pinned UI commits removal on selection rather than confirm, or cancel
returns to a different stage, the static packet must record that fact and the
state machine must be revised before tests or production code. An absent button
is not inferred. Pagination, filtering, bottle/lock restrictions, cards that
cannot be removed, and a deck too large for the bounded visible surface remain
unsupported until their exact public UI behavior is established.

### 3.8 Full potion inventory and generic child handoff

Potion stock is observed but never legal in the first slice. After the shared
item contract freezes:

- an affordable enabled potion is legal only when capacity is publicly known
  and there is an empty slot, or the game advertises an explicit supported
  replacement child;
- a full belt with no explicit supported replacement path produces a visible
  but non-legal purchase candidate;
- the shop does not invent discard, replacement, decline, or skip controls;
- the item child owns item-slot selection and cancellation semantics;
- the shop owns price/debit correlation and remains pending until the item
  child returns a terminal result and acquisition is reconciled; and
- child abandonment or uncertainty leaves the parent transaction unresolved.

Whether an accepted purchase debits before the child, after the child, or only
on child confirmation is a blocking target fact. The contract must observe and
accept the actual established ordering without exposing a second purchase or
double-counting the original action.

### 3.9 Leave and completion

An accepted leave dispatch is not completion. Proposed completion requires:

- an accepted `leave` bound to this exact shop incarnation;
- the shop and every shop-owned child are no longer interactive;
- no purchase or removal transaction is pending or uncertain;
- the same run exposes the authoritative post-shop travel surface established
  by the static packet (preferably open, travel-enabled, nontraveling map); and
- no unsupported foreground overlay contradicts the transition.

Passive screen disappearance, a manually opened map, child completion, or a
new unrelated room is not sufficient. If the static packet cannot establish
authoritative leave completion, the first slice may observe and purchase but
must stop after accepted leave as unreconciled rather than claim shop/room
completion.

## 4. Proposed host controller and parent handoff

Add a dedicated bounded `apply_shop_live.py` rather than folding merchant logic
into `apply_room_live.py`. It should reuse the existing private transport but
have strict shop parsing, a separate provider, one fixed deadline, an accepted
shop-action cap, no retry, and distinct attempted/accepted/reconciled counts.

The first deterministic provider can be `first-card`: rank legal affordable
card purchases by the advertised candidate order, purchase at most one card,
then leave. A separate `leave` provider buys nothing. This is fixture behavior,
not a gameplay-quality claim. The host never computes affordability or legality
independently; it consumes `legal_actions`.

The proposed run handoff is:

```text
accepted/reconciled map selection(kind=shop)
  -> wait for fresh ready shop decision
  -> run bounded shop controller
  -> require shop complete
  -> require fresh map decision
  -> resume existing run loop under the existing destination cap
```

The map selection that enters the shop remains one map action and consumes one
existing destination slot. Each accepted shop mutation is counted once as a
shop action. A child controller's own actions are child actions; returning from
the child must not add another copy of the initiating purchase to shop or total
action counts. An accepted child result cannot mark the parent shop action
reconciled, the shop complete, or the room/floor complete.

The host must return a truthful partial prefix on failure. It does not adopt an
earlier uncertain shop action, phase-scan, reopen a shop, or route-explore. Exact
run-summary field/version impact is a coordinator-owned shared-contract
decision. Until resolved, do not add shop counters to existing accepted run
schemas or overload `room_action_count`.

## 5. Shared questions for coordinator freeze

These choices affect `MR-LOOT-02` and/or `MR-EVENT-03` and are not decided here:

1. **Lineage:** exact parent decision/action identity carried into an item child
   and the terminal child result carried back. Recommendation: opaque bounded
   `parent_handoff_id` generated from the parent decision/action/category, with
   no native instance ID; child identity remains independent.
2. **Reservation:** whether a parent reserves before child entry and how that
   reservation survives cancel, abandonment, timeout, and process teardown.
   Recommendation: reserve once before initiating purchase and never release on
   uncertainty; cancel may reconcile a non-purchase only if public state proves
   no debit/acquisition.
3. **Accounting:** one accepted initiating parent action plus separately counted
   child actions, never an additional action for return/reconciliation. The
   coordinator must choose run-summary fields and preserve old schema exactness.
4. **Completion:** a child terminal result is evidence only about the child.
   Parent payment/acquisition and enclosing shop leave/completion each require
   their own evidence.
5. **Capacity/public inventory:** one shared optional shape for potion slots,
   capacity, and full-state; absence is unknown, never zero or empty.
6. **Debit/acquisition ordering:** whether the shared item handoff represents
   pre-debit, post-debit, or either ordering and which component owns the pending
   deadline. Recommendation: shop owns the single outer deadline and payment
   correlation; item child owns only its advertised choice lifecycle.
7. **Abandonment:** exact result when a child is canceled versus disappears,
   becomes unsupported, or times out. Recommendation: only an explicitly
   advertised cancel with unchanged parent invariants is reconciled cancellation;
   every other abandonment is uncertain and non-resumable.

## 6. Synthetic acceptance specification

All cases use actual public service/host entry points over in-memory surfaces or
literal fake transport. Fixtures may use private test seams to model target
objects, but assertions are exclusively on public bodies, request bytes,
dispatch counts, state-machine output, and cleanup. Passing them would be
`bridge_fixture`, not live or differential evidence.

| ID | Case and setup | Required result |
| --- | --- | --- |
| `SHOP-PASSIVE-01` | Repeated decision reads while a ready shop is already open | Byte-identical ready body; zero open/populate/click calls; no gold, stock, deck, relic, potion, overlay, map, or revision mutation. |
| `SHOP-PASSIVE-02` | Read from menu, combat, map, event, reward, transition, or hidden shop | `waiting`/typed unsupported as contracted, empty candidates/actions, zero UI mutation. |
| `SHOP-VISIBLE-03` | Mixed card/relic/potion stock plus removal and leave | Every visible bounded slot appears once in presentation order with exact kind/key/price/affordable/enabled/supported; first-slice legal actions contain only eligible cards and leave. |
| `SHOP-AFFORD-04` | Prices below, equal to, and above current gold; native-disabled slot | Arithmetic affordability is exact; equality is affordable; disabled/unsupported candidates are not legal. |
| `SHOP-DUP-05` | Two visible cards with the same key and equal price | Distinct public slot/action IDs; selecting the second resolves/clicks only the second control; key-only targeting is rejected. |
| `SHOP-BUY-06` | Legal card purchase; acquisition appears before debit | One dispatch/accepted receipt; waiting with no actions after the first half; one reconciliation only after exact debit; next decision revision is coherent. |
| `SHOP-BUY-07` | Legal card purchase; debit appears before acquisition | Symmetric to `06`; no atomic-order assumption and no second dispatch. |
| `SHOP-BUY-08` | Debit and acquisition appear in one observation | One accepted and one reconciled shop action; exact deck/model/gold deltas; sold slot coherently absent/disabled. |
| `SHOP-LEAVE-09` | Legal leave reaches authoritative fresh map | One dispatch; completion only after same-shop accepted leave and contracted map evidence; no pending transaction. |
| `SHOP-STALE-10` | Price, gold, enabled state, stock key, or affordability changes between read and apply | Immediate full revalidation rejects stale; zero reservation, click, debit, acquisition, and action-budget use. |
| `SHOP-REORDER-11` | Stock slots reorder between read and apply | Old decision and slot action are stale; no fallback by key/index and no click. Fresh decision reflects new order/hash. |
| `SHOP-SOLD-12` | Requested slot disappears or becomes sold/disabled before apply | Stale with zero mutation/budget; never selects the item now occupying the old index. |
| `SHOP-OVERLAY-13` | Map, removal child, item child, unknown overlay, or transition becomes foreground immediately before click | Stale or typed unsupported before reservation; zero click. If after accepted click, pending state exposes no actions and follows reconciliation/uncertainty rules. |
| `SHOP-REJECT-14` | Canonical rejected receipt from bridge | Attempted increments only; no accepted/reconciled count, no retry, and controller stops with fixed failure. |
| `SHOP-DUP-15` | Same accepted request is submitted twice to public apply | First dispatches once; second is `already_applied` even after projection change; total click count one. |
| `SHOP-LOST-16` | Dispatch occurs but response is lost/transport closes | Host stops uncertain with attempted only, closes socket, makes no read or retry; producer reservation prevents a same-process duplicate if directly probed by fixture. |
| `SHOP-UNCERTAIN-17` | Only debit or only acquisition persists to deadline | Never reconciled/completed; no legal actions/retry/refund; fixed uncertainty result and truthful counts. |
| `SHOP-WRONG-18` | Wrong debit, wrong card key, deck delta >1, or unrelated contradictory player delta | Permanent fail-closed reconciliation error; no second mutation and no success summary. |
| `SHOP-CHILD-19` | Purchase opens an item/overflow child before effects settle | Parent stays reserved/pending and advertises no shop action; child result alone does not reconcile purchase or complete shop. |
| `SHOP-FULL-20` | Potion belt is full | Potion remains visible; no purchase action unless a frozen explicit replacement child is ready. No inferred discard/replace/skip. |
| `SHOP-REMOVE-21` | Removal open -> select duplicate card -> confirm with debit/removal in either order | Once later enabled: each stage has a fresh decision; visible slot plus key binds duplicate; exact debit/deck/key deltas reconcile once. Before freeze, all removal actions are absent from legal actions. |
| `SHOP-CANCEL-22` | Explicit cancel from removal select/confirm | Once later enabled: exact advertised cancel only; return stage and unchanged gold/deck reconcile. Disappearance without explicit cancel stays uncertain. |
| `SHOP-MALFORMED-23` | Null/wrong types, unknown fields where disallowed, bad hash, bad action grammar, mismatched slot/index, negative/oversized price, duplicate IDs/actions, noncontiguous indices, invalid ASCII/key length | Parser/encoder rejects with fixed bounded error; no game-thread mutation or arbitrary exception text. |
| `SHOP-BOUNDS-24` | Exactly every frozen max, then max+1 candidate/session/revision/reservation/body | Boundary value is accepted and canonical; overflow yields unsupported/fixed rejection without truncation, partial body, mutation, or unbounded retention. |
| `SHOP-REPLAY-25` | Ready A -> overlay/waiting -> same A; shop A -> B -> A; accepted A -> disappearance -> A | Public ordinal/decision rules do not mint a replayable purchase. Previously accepted A remains reserved; new shop incarnation is distinct and bounded. |
| `SHOP-READ-RACE-26` | Concurrent reads during apply and two concurrent apply requests | Reads are passive; the gate admits at most one reservation/dispatch; loser is stale/already applied, never a second click. |
| `SHOP-HANDOFF-27` | Map -> shop -> purchase -> child -> leave -> map | One map-enter action, one purchase action, each child action once, one leave; child return adds zero; parent completion waits for purchase and leave reconciliation. |
| `SHOP-HOST-28` | Waiting, unsupported, malformed, rejected, uncertain, timeout, cancellation at each host stage | Stop at first failure, no phase scan/fallback/retry; exact attempted/accepted/reconciled inequalities; no partial success promoted. |
| `SHOP-CLEAN-29` | Success and every exceptional exit with canaries in request/response/exception objects | Every socket closes; mutable sent/credential/response buffers are zeroed under established limits; no canary/raw body/control/native identity appears in output. |
| `SHOP-COMPAT-30` | Existing `0.8.0` vectors, routes, room/reward clients, providers, and run outputs against proposed-source negative control and integrated source | Old artifacts remain byte-exact until an explicit versioned successor; new behavior appears only in successor vectors/provider and cannot alter accepted defaults. |

Independent review must mutate each oracle: remove immediate revalidation,
retarget by model key, treat receipt as effect, count return as an action, release
reservation after loss, accept one-sided transfer, complete on disappearance,
or let a read open the merchant. Each mutation must fail at least one dedicated
case.

## 7. Dependency-ordered implementation plan and future ownership

No file listed here is authorized for change by this proposal. Exact ownership
must be reassigned after the three proposals are reviewed together.

### Gate A — target-build static member packet (hard dependency)

- Audit only already-approved/reviewed source or compile metadata for the eight
  unknowns in Section 2.3.
- Record exact types/members, public-visibility basis, read passivity, control
  ordering, and observed/static limitations in a new coordinator-approved
  research record.
- Independently review license/provenance and prove that no installed-game,
  profile, save, credential, endpoint, or live access occurred.

### Gate B — shared contract freeze (hard dependency)

- Coordinator resolves Section 5 with `MR-LOOT-02` and `MR-EVENT-03`.
- Freeze route names, DTO fields, bounds, action grammar, parent/child lineage,
  accounting, completion, version and artifact policy.
- Add exact proposed vectors and a negative control before producer code.

### Gate C — first-slice C# producer

Proposed exclusive shop-producer ownership:

- new `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicShopDecision.cs`
- new `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicShopAction.cs`
- new `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicShopDecisionReader.cs`
- new `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicShopActionApplier.cs`
- new `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicShopInteractionSession.cs`
- new `bridge/Sts2AgentBridge/tests/Sts2AgentBridge.Tests/Public/ShopInteractionTestSuite.cs`

Shared contract/integration-owner files, not implicitly owned by the producer:

- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/ProbeRoutes.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/CanonicalProbeEncoder.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Transport/ProbeRequestParser.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Transport/ProbeRequestProcessor.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Transport/BoundedLoopbackServer.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Bootstrap/BridgeBootstrap.cs`
- `bridge/Sts2AgentBridge/src/Sts2AgentBridge/Sts2AgentBridge.csproj`
- exact `bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors/*` additions
- contract, transport, artifact-binding and public test-suite registries under
  `bridge/Sts2AgentBridge/tests/Sts2AgentBridge.Tests/`

Acceptance: passive browse, duplicate/stale/reordered stock, one direct card
purchase in either effect order, leave, reservation/replay, bounds, malformed,
overlay race and negative-control cases pass. Relic, potion, and removal
candidates are visible but never legal.

### Gate D — independent actual-client/transport gate

Proposed new files:

- `bridge/Sts2AgentBridge/tools/apply_shop_wire_fixtures.py`
- `tests/backends/live/test_apply_shop_wire_fixtures.py`

It must invoke actual request/parser/apply entry points with literal bytes and
fake transport; it may not reproduce the producer state machine. Cover all
receipt/transport/timeout/cancellation/cleanup and parent accounting cases,
including a negative control against exact `0.8.0` production.

### Gate E — host shop controller and provider

Proposed shop-host ownership:

- new `bridge/Sts2AgentBridge/tools/apply_shop_live.py`
- new `bridge/Sts2AgentBridge/tools/apply_shop_live_fixtures.py`
- focused additions to `bridge/Sts2AgentBridge/tools/decision_providers.py`
  and `decision_providers_fixtures.py`
- new focused pytest wrappers under `tests/backends/live/`

Shared run integration remains coordinator-owned:

- `bridge/Sts2AgentBridge/tools/apply_run_live.py`
- `bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py`
- run wire/acceptance/diagnostic consumers and their tests

Acceptance: provider consumes only advertised legal actions; exact attempt /
accepted / reconciliation accounting; one-purchase bound; no retry or phase
scan; existing providers/default outputs exact.

### Gate F — later slices

1. Direct relic purchase after public relic ownership evidence freezes.
2. Potion purchase after `MR-LOOT-02` item capacity/acquisition/overflow child is
   accepted and the coordinator freezes shared lineage/accounting.
3. Card-removal open/select/confirm/cancel after the exact static UI lifecycle,
   visible deck bounds/paging, and atomicity-independent reconciliation are
   accepted.

Each later slice needs producer tests, an independent actual-client gate,
aggregate bridge tests, whole-diff information-boundary review, reproducible
package/artifact binding, and a separately authorized live campaign. Do not
bundle all three into the first bridge-version increment.

## 8. Future live acceptance boundary (not authorized)

The first later live test needs exactly this fresh state, prepared by the user
after a coordinator-approved overlay is staged:

> Profile 3, Ironclad, Ascension 0, inside an ordinary shop reached through a
> selected shop map node; the merchant inventory is fully visible and untouched;
> no item/removal child or other overlay is open; at least one ordinary card is
> visibly enabled and priced at or below the displayed current gold; and the
> native leave control is visible and enabled.

The coordinator must visually confirm those public conditions without opening
the shop through a bridge read. Invoke the maintained shop controller once with
the reviewed one-card provider. The success target is one reconciled direct card
purchase, one reconciled leave, and a fresh travel-ready map under the frozen
parent handoff. If no affordable card is present, a leave-only case may test
passivity/completion but must not count as purchase acceptance; do not farm a
run. If a relic/potion/removal child appears, stock changes unexpectedly, or any
receipt/effect is uncertain, stop without retry.

Any future campaign retains the existing explicit user approval, pinned build,
exact package/config/credential, Profile 3, capture-off/no-retention, fixed
deadline/action cap, normal quit, exact quarantine/purge, stopped/closed/base
verification, no Cloud/profile/save access, and no remote Git boundaries. The
current user's repeated clean-unmodded-launch waiver is recorded as omitted,
not passed. None of those operations is authorized by this proposal.

## 9. Exclusions and claim boundary

- No item controls are defined independently of `MR-LOOT-02`.
- No potion use/discard, reward redesign, treasure, boss/act transition, rest
  upgrade submodal, nested combat choice, generic modal router, recovery
  journal, retry, action adoption, or automatic phase detection.
- No private merchant/item/card instance ID, seed, hidden stock/RNG, profile,
  save, history, platform identity, or unrevealed content enters public state.
- No production file, test, contract/vector, package pin, bridge version,
  provider, export, dependency, or shared documentation is changed here.
- `live_probe_v0`, bridge `0.8.0`, `headless_v0`, D47, and every accepted default
  remain exact today.
- This proposal does not prove that the named target APIs exist, that reads are
  passive, that a transaction works, or that a shop can be completed live.

The coordinator should freeze only the first slice after the static member and
shared-contract gates. Everything else remains a named, bounded later packet.
