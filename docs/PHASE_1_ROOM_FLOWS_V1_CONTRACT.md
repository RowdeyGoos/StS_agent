# Room flows V1 functional contract

Date: 2026-09-05. Status: functional implementation, wire schemas and hosts independently reviewed; aggregate source verification follows.
Component: `room_flows_v1`, separate from unchanged 0.8.0 and five frozen item
trees. This contract selects working shop/event cores, real native adapters,
wire/hosts and cross-language tests; it does not by itself enable a live package.
The [implementation plan](PHASE_1_SHOP_EVENT_IMPLEMENTATION_PLAN.md) owns scope
and disjoint writer paths. Native facts belong in the sanitized static ledger.

## Common interface and invariants

Namespace `Sts2AgentBridge.Successors.RoomFlowsV1`. Coordinator owns:

```csharp
public interface IRoomFlowReadValue { }
public interface IRoomFlowApplyValue { }
public interface IRoomFlowSession : IDisposable {
    string FlowKind { get; }
    IRoomFlowReadValue Read();
    IRoomFlowApplyValue Apply(string? decisionId, string? actionId);
}
```

`RoomFlowDispatchReceipt` implements IRoomFlowApplyValue and has immutable
FlowKind (`shop` or `event`), SessionNonce (32 lowercase hex), ParentOrdinal (1),
DecisionId (64 lowercase hex), ActionId and Outcome (`accepted`).
`RoomFlowApplyFailure` has only FlowKind, SessionNonce, ParentOrdinal and fixed
Outcome (`rejected`, `uncertain` or `unsupported`), with no arbitrary request or
exception text. Modules use separate discriminated observation types; no
nullable shop/event union. Constructor inputs and returned sequences are copied.
All native references/delegates and private captures remain unencoded.

Exactly one selected flow owns an activation. No automatic initial screen
adoption, phase fallback or runtime reset. All Read/Apply/dispose native work
runs on the owner frame thread. Dispose suppresses future work and releases
owned native subscriptions; exceptions cannot be represented as successful
cleanup. Immediate full public/native-binding recapture precedes reservation.
Reserve before dispatch and retain every reservation across failure, gaps,
children and repeated reads. Reentrant calls cannot acquire action authority.
Post-reservation errors/uncertainty latch terminally; no retry or late adoption.
Each pending operation allows at most 256 reads; its final allowed read can
resolve. Host uses one overall deadline and owns attempted/accepted/reconciled
exchange counts separately from producer reservation budgets.

## Shop module

Namespace `.Shop`. `ShopV1Session(nonce, IShopV1NativeAdapter)` implements the
common interface. Start only inside one already-open ordinary shop inventory,
with map closed/travel-disabled/not-traveling and no foreground overlay/modal.
Capture the same run, room, inventory node/model, player and map references.
Enumerate at most 32 native stock slots, preserve their indices, and copy at
most 512 deck references/keys. Keys use the frozen item ASCII key alphabet,
length1..128. Public player state is gold and deck count, both nonnegative
bounded integers. All supported prices come from the exact rendered cost label,
canonical ASCII decimal, never MerchantEntry.Cost or a price hook.

`ShopV1Observation` implements IRoomFlowReadValue: Version=`shop_v1`, FlowKind,
SessionNonce, ParentOrdinal, Status, Phase, DecisionId, Player, Offers,
LegalActions and PriorResults. Status is waiting|unsupported|ready|complete;
phases are inventory_browse|purchase_waiting|close_waiting|room_ready_to_leave|
leave_waiting|complete|unknown. Player has Gold and DeckCount. Each offer has
Slot, Kind, Key, DisplayedPrice, Affordable, Enabled and Supported. Visible
relic/potion/removal/unknown slots remain explicit and nonlegal; only ordinary
cards may be bought. Empty or bound inactive views have no offers/actions or
decision, with fixed empty player facts when context is unavailable.

Actions are exactly buy:card:<native-slot0..31>, inventory:close and leave.
The policy allows zero or one affordable ordinary-card purchase, then one
inventory close, then one room leave. At most 3 total reservations. No second
purchase even after restock. The selected purchase input is exactly one call
to the retained NMerchantCard slot's inherited public _GuiInput, with one fresh
Godot.InputEventAction whose Action is the public static MegaInput.select
StringName and Pressed=true. Allocate after reservation and dispose the input
event even on failure. The selected handler routes this exact action once to
OnSelected; no mouse hover state is synthesized. Never use global/tree input,
coordinates, debug helpers, a second input event, private calls or reflection.
The exact public MegaInput.select declaration is a final native compile gate.
ForceClick is explicitly invalid for the card Hitbox because it emits the
wrong signal; inventory Back and room Proceed still use their proven ForceClick.

Before purchase retain exact stock/entry/CreationResult.Card, controls/labels,
rendered prices, gold and copied deck. Subscribe to the exact entry's public
PurchaseCompleted signal after reservation and before dispatch if the reviewed
body establishes the post-hook completion ordering. Require exact success
entry plus gold debit by displayed price, exactly one offered-model insertion
into the otherwise identical deck, and a declared stock disposition before
reconciliation. One-sided effects wait; contradictory deltas fail. Restock
cannot create a second legal purchase. Never invoke private purchase methods,
commands, inventory mutation or price hooks directly.

Inventory close uses exact visible/enabled BackButton ForceClick. Reconcile
same inventory IsOpen true-to-false and restored room controls, without a map
transition; that result does not complete the room. Only then may leave become
ready. Recapture same visible/enabled Proceed, context and closed map; reserve
and ForceClick once. No bridge FTUE/profile query. A modal/tutorial or failure
to reach the exact action-bound same-map open/travel-enabled/nontraveling
poststate stops unsupported or times out with the reservation retained. An
accepted leave receipt is not yet reconciliation. No dismissal or retry.

`PriorResults` is an immutable sequence of length0 or1. Its single entry binds
flow/nonce/ordinal/decision/action and kind purchase_card|inventory_close|leave,
result reconciled. It is a terminal result for that exact prior action, never
a cumulative counter or whole-room claim. Keep it attached to all next-ready
reads until the next action is accepted; clear it only on that reservation.
Complete carries the exact leave result. The host must validate each prior
result against its own accepted receipt before choosing the next action.

## Event module

Namespace `.Event`. One retained run/player/event-room/map, ParentOrdinal1,
no custom event, embedded combat, initial child or foreground map adoption.
Read at most 8 option buttons with index, StableId (the native TextKey), bounded rendered text,
locked/enabled/dangerous and IsProceed flags. Rendered text is UTF-8, bounded
without truncation, allowing normal newlines but rejecting invalid scalars and
controls; exact byte limit and exported classes are fixed in the API addendum.
No parsed cost/effect or policy-quality claim follows from text.

Maintain a full display decision digest including text for stale checking, and
per-parent lifetime reservations by stable option key. Never renew a reserved
key through text/order/legality changes or A-to-B-to-A. An eligible previously
unseen key can be selected once from a changed current projection. No event
step ordinal or generic monotonic-progress claim. Reserve ordinary options and
synthetic Proceed before native ForceClick; at most 12 parent dispatches. Report
ordinary choices as accepted with separately observed transitions, not as
reconciled effects.

At most one controller-owned item child can be created after an accepted
ordinary option, with uninterrupted controller ownership, first supported
foreground transition, same retained run/player/event-room and exact topmost
NRewardsScreen. This is explicit local control ownership, not proof that the
option caused the reward. Use exactly one frozen ItemWireV1Service, which owns
the actual ItemV1Session; do not create a second item session. Preserve its
GET/POST routes and bytes. The coordinator's broker validates exact accepted
receipt and resolved result before authorizing parent revalidation. Child
uncertainty/failure is terminal for the parent. Item collection neither
reconciles the ordinary option nor renews its key or proves event completion.
Parent max12 and child max1 remain separate; the host aggregate max is13.

Final exit requires the same event's exact statically constructed singleton
PROCEED option, IsFinished=true, IsProceed=true, and map closed/travel-disabled/
nontraveling before dispatch. Only its reserved normal native click followed
by the same map open/travel-enabled/nontraveling yields a correlated map_handoff.
A map opened after another option or after item completion is insufficient.
Parent item revalidation may expose a previously unseen eligible choice or the
exact final Proceed; unchanged reserved choices remain nonactionable.

## Integration gate

Coordinator implements strict per-flow canonical wire schemas, services and
Python hosts over the real module types. Frozen item bytes/host behavior remain
unchanged. A single outer exchange/credential and shared deadline constrain the
nested child; no reset extends it. Actual C# service bytes must pass real Python
parsers/controllers, including exact item child success and uncertainty. Source
snapshot/checker and native compile gates preserve all old inventories. Release
transport/bootstrap/package are one later combined gate, never inferred from
pure-core or host fixtures. No current game setup is requested.


## Event API and broker addendum

`EventV1Session(nonce, IEventV1NativeAdapter, IEventItemChildFactory)` implements
the common interface. EventV1Observation has Version=`event_v1`, FlowKind=event,
SessionNonce, ParentOrdinal1, Status, Phase, DecisionId, Candidates and
LegalActions. Status waiting|ready|unsupported|item_child; ready Phase is
choose_option|proceed. Other phases are waiting|item_child|unknown. Each
EventV1Candidate has CandidateIndex, ActionId=choose:<index>, StableId (the exact native TextKey and lifetime reservation key),
RenderedText, Enabled, IsDangerous and IsProceed. Bound text to 1024 UTF-8 bytes;
reject null/empty text, invalid scalars, NUL and control characters except LF. Preserve
BBCode and original text without normalization or truncation. The field is the
visible label's exact text source, not a claim about plain rendered glyphs.
Duplicates of stable option keys in one projection are unsupported. A separate
EventV1ResolvedResult implements IRoomFlowReadValue and binds Version, FlowKind,
SessionNonce, ParentOrdinal, DecisionId, ActionId and Result=map_handoff.

The coordinator owns these pure broker interfaces in the common namespace:

```csharp
public interface IEventItemChildFactory {
    IEventItemChildBroker Create(RoomFlowDispatchReceipt parentReceipt,
                                IItemV1NativeAdapter adapter);
}
public interface IEventItemChildBroker : IDisposable {
    RoomFlowDispatchReceipt ParentReceipt { get; }
    EventItemChildStatus Status { get; }
    byte[] Handle(string? method, string? route,
                  string? decisionId, string? actionId);
}
```

`EventItemChildStatus` is an abstract immutable class with ParentReceipt.
`EventItemChildActive`, `EventItemChildResolved` and `EventItemChildFailed`
are concrete variants; Failed additionally has fixed RoomFlowApplyFailure.
The event session requires reference equality to its exact accepted parent
receipt for broker and every status. The factory is called at most once.
The event native adapter supplies a child adapter bound to the just-classified
exact run/player/event-room/reward-screen, so a later first GET cannot adopt a
replacement screen. Before item dispatch that wrapper retains the full initial
child binding. During reconciliation it honors the frozen item rule: retain
reward/player/model facts and do not dereference freed screen/button objects.
The broker has one ItemWireV1Service, delegates original requests/bytes, and
changes passive local status only after validating its exact ready/accepted/
resolved envelopes. The event session exposes its broker only while child
ownership is active; parent actions are unavailable then. No copied/fabricated
parent receipt or mismatched child receipt/result can resume the parent.

The broker accepts one POST and permanently fails after an invalid, rejected,
uncertain, unsupported or malformed child outcome. Resolved requires the same
nonce, ordinal1, original published decision/action, offer identity and exact
collected result; receipt alone is never resolution. The actual frozen item
service enforces native reconciliation; the broker independently binds the
observed protocol transition to this one parent continuation. Child status
reads are passive/local; no target reads or action occur through Status.

A module terminal failure or disposal releases its broker/subscriptions once.
The composite router owns external serialization and terminal transport state,
while module reservation ledgers protect their native action limits. No native
adapter has a network, filesystem, game-launch or generic input API.


## Accepted body bounds and static closure

Shop and event successor routes have maximum 65536-byte UTF-8 response bodies;
frozen item routes remain byte-exact with their4096-byte limit. Event source
text is at most 8 times1024 UTF-8 bytes, each StableId at most96 printable ASCII
characters, with fixed field names and enums. Even maximal six-byte JSON
escaping of every permitted source byte plus bounded keys/fields fits65536.
Shop has at most 32 offers with128-byte keys, bounded integer fields and fixed
metadata, also below that limit. The core applies these count/string/integer
bounds; the codec independently rejects any over-limit body. Unknown variants
or unbounded future fields require a successor contract, not silent growth.

Independent review accepted the common/event interfaces and the per-control
shop input path. The final member check proved MegaInput.select is public
static readonly Godot.StringName. Singleton getters proved event/map identity
matches NRun.EventRoom and NRun.GlobalUi.MapScreen. The follow-up totals21 types
and38 actual method bodies; no target assembly was executed. The selected
control is one native `_GuiInput` call, not a generic input API.

Common receipt construction enforces the exact flow-specific action grammar:
shop buy:card:<canonical0..31>, inventory:close or leave; event
choose:<canonical0..7>. No malformed or non-ASCII action can enter a receipt.
The item broker transfers each returned mutable body to its caller, which must
zero it after parsing/transport. The broker retains no response buffer and
zeros any produced buffer it still owns when an exception prevents return.
Pure tests cover these exact text/action/buffer boundaries.


## Concrete wire and host integration

One RoomFlowWireService owns a single concrete shop or event session.
Parent routes are GET /probe/room-flows-v1/public/decision and
POST /probe/room-flows-v1/public/action. Item routes remain frozen and are
available only after an item_child parent observation from that same accepted
ordinary option. There is no route-based initial adoption or flow switch.

Parent JSON common ordered fields are schema_version=1,
protocol=room_flows_v1, version=shop_v1|event_v1, flow_kind,
session_nonce, parent_ordinal=1, status. Accepted adds decision_id/action_id;
fixed rejected/uncertain/unsupported apply failures add nothing; error adds
code=invalid_request|internal_failure. Shop observations add phase, decision_id,
player{gold,deck_count}, offers, legal_actions, prior_results. Event observations
add phase, decision_id, candidates, legal_actions. Event resolved adds
decision_id/action_id/result=map_handoff. Exact nested field names follow the
immutable module fields in snake_case and the explicit wire codec. No native
object or generic reflected object is encoded.

Wire text follows Python json.dumps ensure_ascii=True with compact separators,
lowercase Unicode escapes, exact key ordering and no extra whitespace.
The event decision digest uses big-endian int32 framing and UTF-8 byte lengths;
the shop digest uses its ASCII length/delimiter framing. Hosts recompute the
corresponding real module digest, reject duplicate/extra/reordered fields and
noncanonical bytes, and zero every returned mutable response buffer.

Event display identity includes text for stale Apply rejection. Continuation
requires a changed structural projection excluding rendered text; text-only
changes cannot expose the next action after a choice or child. Admitting a
changed parent projection revokes the old choice's child eligibility.
Each stable option key remains reserved for the parent lifetime.

The host has one 30-second outer deadline, at most 1024 total exchange reads,
at most 3 shop or 12 event parent POST attempts and at most 1 item POST.
The frozen item host retains its own 15-second bound; every child exchange and
sleep is additionally clamped to the outer deadline. Reuse its actual
run_collection and pure strict decoder from the pinned frozen source, without
changing transport ownership or source bytes. Failed summaries retain only
validated partial-prefix counts and fixed codes; option text, keys, nonce and
raw responses are not retained. Event option transitions are explicitly
observations, distinct from the one reconciled final exit and child collection.

The wire suppresses actions after terminal completion and caches only the
bounded typed terminal result. Cleanup must execute on the owner thread outside
a request. Wrong-thread/reentrant cleanup throws without claiming completion;
a subsequent owner-thread Dispose drains owned resources. Cleanup exceptions
remain observable. No listener, runtime bootstrap, installation or live launch
is enabled by this functional packet.
