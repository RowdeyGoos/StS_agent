# Generic event v6 — singleton item children

2026-09-08. Consumer contracts independently accepted against HEAD f6cc6e4. The scoped item metadata result establishes the native request/creation/completion facts below; final independent native contract acceptance precedes production implementation. All 25 predecessors and the original bridge remain frozen. This functional slice includes no release installation or live campaign.

## Scope and preservation

Add one singleton potion/relic reward child under an accepted generic parent
option, without an event-name catalog. One admitted rewards screen contains
exactly one reward, of supported potion/relic kind; it is not a filtered view
of a larger reward set. Its reward index need not be zero (frozen range 0..255).
A potion requires an available slot; do not discard/replace/use a potion to make
space. No multi-collection item batch, card/gold reward, custom screen or skip.
Native must establish that the single collection can finish the owned offer;
the completion gate below must still observe actual completion, never assume it.

Keep old card family limits and semantics exactly. Protocol becomes
`generic_event_v6`; routes are `/probe/generic-event-v6/public/decision` and
`/probe/generic-event-v6/public/action`. Child payload contracts stay
`card_selection_v1`, `card_transform_v1`, and newly composed `item_v1`.

## Explicit reuse and assembly closure

Source-link frozen card_selection_v1 core Contracts+Session exactly once.
Source-link all three generic_event_v5/transform_core files unchanged, together
with generic_event_v5/core/GenericEventV5ChildSession.cs unchanged: the transform
session implements that frozen interface. A G6 card wrapper accepts that
interface, delegates Read/Apply/Dispose, and admits only its two known versions.
Old card families use its frozen GenericEventV5FrozenChildSession wrapping the
actual CardSelectionV1Session; transform uses actual CardTransformV1Session.
Do not also reference G5.Core, which would duplicate the linked CLR contracts.

Source-link frozen item_v1/core/{ItemV1Contracts,ItemV1CanonicalEncoder,
ItemV1Session}.cs exactly once. Instantiate ItemV1Session, not a replacement.
Wire source-links frozen item_wire_v1/producer/{ItemWireV1Protocol,
ItemWireV1Codec}.cs; adapt DTOs to the frozen envelope as event_orchestrator_v1
already does. Keep original item_probe_v1 protocol, item_v1 version,
surface_ordinal=1, fixed field order, and collect:i grammar inside the payload.
Source-link G5 CardTransformV1WireCodec unchanged and call its G5 namespace;
retain existing frozen card codec/protocol/parent-contract links exactly once.
Host loads hash-pinned frozen item_wire_v1/host/item_host.py and calls its strict
_decode_response helper only. It does not run its standalone controller or
routes. Likewise use frozen G5 child-only card_transform_host.py unchanged and
frozen card_selection_v1/host/card_selection_host.py. All new external reused
files enter the exact provenance/compiled-closure checks.

## Accepted public C# API (G6 namespace unless otherwise stated)

```csharp
public interface IGenericEventV6ChildSession : IDisposable {
    string ContractVersion { get; }
}
public interface IGenericEventV6CardChildSession : IGenericEventV6ChildSession {
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}
public interface IGenericEventV6ItemChildSession : IGenericEventV6ChildSession {
    IItemV1ReadValue Read();
    IItemV1ApplyValue Apply(string? decisionId, string? actionId);
}
public sealed class GenericEventV6CardChildSession : IGenericEventV6CardChildSession {
    public GenericEventV6CardChildSession(IGenericEventV5ChildSession session);
    // ContractVersion/Read/Apply/Dispose delegate to the one owned session.
}
public sealed class GenericEventV6ItemChildSession : IGenericEventV6ItemChildSession {
    public GenericEventV6ItemChildSession(string sessionNonce,
        IGenericEventV6ItemNativeAdapter adapter);
    // Constructs exactly one ItemV1Session over a revocable guarded adapter.
}
public abstract record GenericEventV6ChildRead(string ContractVersion);
public sealed record GenericEventV6CardRead(string Version,
    ICardSelectionV1ReadValue Value) : GenericEventV6ChildRead(Version);
public sealed record GenericEventV6ItemRead(IItemV1ReadValue Value)
    : GenericEventV6ChildRead("item_v1");
public abstract record GenericEventV6ChildApply(string ContractVersion);
public sealed record GenericEventV6CardApply(string Version,
    ICardSelectionV1ApplyValue Value) : GenericEventV6ChildApply(Version);
public sealed record GenericEventV6ItemApply(IItemV1ApplyValue Value)
    : GenericEventV6ChildApply("item_v1");
public abstract record GenericEventV6Admission(object Identity);
public sealed record GenericEventV6CardAdmission(object AdmissionIdentity,
    string Operation, int MinSelect, int MaxSelect, string CommitMode,
    int DomainCount) : GenericEventV6Admission(AdmissionIdentity);
public sealed record GenericEventV6ItemAdmission(object AdmissionIdentity,
    int OfferCount) : GenericEventV6Admission(AdmissionIdentity); // exactly 1
```

NativeCapture retains G5 fields but Admission is this closed union. The native
factory keeps `IGenericEventV6ChildSession CreateChild(object admissionIdentity)`.
Parent ReadChild/ApplyChild keep exact lineage arguments and return the above
unions. Validate known concrete union cases and matching descriptor/interface/
version at every boundary, including failure values; reject unknown derived cases.
A facade implementing both typed interfaces is invalid. Native admission and
screen reference tombstones remain shared across card and item children.

## Native completion API for B

```csharp
public enum GenericEventV6ItemTaskState { Pending, Succeeded, Faulted, Canceled }
public sealed record GenericEventV6ItemTaskWitness(object Identity,
    GenericEventV6ItemTaskState State);
public sealed record GenericEventV6ItemCompletion(bool OwnershipValid,
    bool EffectStillValid, bool ScreenClosed, GenericEventV6ItemTaskWitness? Collection,
    GenericEventV6ItemTaskWitness? Offer, GenericEventV6ItemTaskWitness? Chosen);
public interface IGenericEventV6ItemNativeAdapter : IItemV1NativeAdapter, IDisposable {
    GenericEventV6ItemCompletion CaptureCompletion();
}
```

All witness identities are native-only. B binds the exact accepted option,
run/player/event/room/map, RewardsSet.Offer invocation/task, foreground screen,
sole reward/model/control, collection invocation/task and parent Chosen task.
CaptureCompletion reports only those owned tasks, not arbitrary completed tasks.
Missing task is pending; once observed, a role's identity cannot change/disappear. Compare native witness identities by reference equality.
Pending may become terminal without an intermediate observed frame. Terminal
states must remain exactly the same; they cannot change to another terminal state or regress. No cross-role distinct-task assumption is imposed. Across item episodes a naturally cached successful Task may recur: exact fresh observed invocation, request/screen/reward and collection-ticket ownership distinguish those generations. Per-role returned Task identity remains immutable within its episode. Existing card task-reuse rules are unchanged.
OwnershipValid=false, unknown enum, canceled/faulted task, changed task binding or
foreign foreground invalidates the episode. ScreenClosed means the exact owned
screen has closed without a substitute child surface; native checks parent
ownership still holds. Native completion does not authorize another dispatch. On every completion
sample after local resolution, EffectStillValid must freshly revalidate the
exact claimed offered identity/key and the preserved potion-slot baseline plus
its one exact insertion (for potion), not merely reuse a prior success flag.
The adapter retains the original pending binding/baseline for this purpose.
EffectStillValid=false after local resolution invalidates the episode even if
all tasks are still pending; before local resolution it conveys no authority.
Exact task/Boolean mappings are established by the reviewed seven-body item capture described below.

## One post-dispatch reconciliation budget

The wrapper enforces owner thread, reentrancy failure, one reserved dispatch and
retryable cleanup retaining adapter ownership until Dispose succeeds. ItemV1Session
has no Dispose, so successful cleanup revokes adapter access and releases native
resources; do not copy the old broker's terminal-read rejection behavior.

After an accepted item dispatch, every wrapper Read consumes one of exactly 256
post-dispatch reads. Before local resolution, call frozen session.Read exactly
once per such Read. Cache its first ItemV1ResolvedResult; never reconstruct it.
Sample CaptureCompletion exactly once on every accepted post-dispatch wrapper Read, including reads where the local frozen result is still waiting. Subsequent reads
can use the cached local result but still consume the SAME remaining budget.
Return frozen waiting while any local/task/screen condition is pending. Publish
the cached result only when local effect is resolved, all three owned tasks are
Succeeded, and ScreenClosed/OwnershipValid/EffectStillValid hold in that read.
Incomplete read256
latches unsupported; complete read256 may resolve. Never perform read257 native
sampling and never start a fresh completion budget after local resolution.
No counter reset on task/effect progress. Pre-dispatch validation is outside this
post-dispatch count. Repeated reads after fully published resolution return the
cached terminal result without incrementing counters or re-sampling native state.
Parent CompleteParent remains the existing final ownership check/reconciliation;
its later failure must preserve already published item completion evidence.

## Strict outer schema, policy and replay scope

Card child fields in exact order: ordinal,parent_decision_id,parent_action_id,
kind,contract_version,operation,min_select,max_select,commit_mode,domain_count.
kind=`card_selection`; version is derived exactly from the supported operation.
Item fields: ordinal,parent_decision_id,parent_action_id,kind,contract_version,
offer_count. kind=`item`, contract_version=`item_v1`, offer_count=1.
No unused card fields on item descriptors. Both use the same shared ordinal1..4.
Request child correlation remains the existing exact outer lineage. Inner item
surface_ordinal remains1 even when outer ordinal is2..4. Unknown fields fail.

For item only, wire/host replay keys are (parent_decision_id,parent_action_id,
ordinal,contract_version,decision_id); preserve parent/card global decision-ID
reservation behavior. Do not alter frozen inner nonce/hash. Validate the strict
item parser and additionally singleton shape immutability, exact admitted count,
one accepted collect:i, and terminal index/kind/key matching its advertised offer.
Item failure status is rejected/unsupported/uncertain, not a card outcome field.
Policy DecisionView.kind becomes `item` for item decisions; card/parent unchanged.
Every malformed/tagged/uncertain boundary stops without another POST.

## Accounting and limits

Keep completed_card_children and add completed_item_children (each0..4).
Maintain disjoint completed lineage sets, their union size<=child_episodes<=4.
Item credit and its one child_reconciled action occur once on first fully gated
resolved ReadChild. Card history reconciliation is unchanged. No item prior-
results list is invented. A child episode never admits another item sub-session.

Each wire/host parent snapshot must equal its previously validated completion
sets before that envelope's child read. The resolved envelope may therefore
carry the prior count; the following snapshot must carry the increment. Same
G5 lag applies to action reconciliation. Parent child_completed history equals
the union of validated completion owners, allowing only the latest owner missing
on unsupported cleanup/CompleteParent failure as in G5. History cannot invent,
duplicate, skip or reclassify a completed owner. Later failure and Proceed retain
both counts. effects retains last-parent-action meaning; item completion sets
item_effect_verified, then a later parent action resets it exactly as before.

Keep 30seconds,2048reads,12parentactions,4sharedchildren,52totalattempts. Card
limits unchanged; item accepts at most one collection. No nested host/controller,
deadline reset, or budget reset at child changes. Summaries expose both cumulative
counts; no raw native task/screen/model identities or exception data.

## Required tests and acceptance

Preserve all G5 suites. Add pure item-wrapper tests using actual frozen session:
local resolve early/task finish late; mutate claim/potion slots after local
resolution while Offer is pending; resolve and finish on256; incomplete256;
no257 capture; missing/changed/faulted/canceled/regressing tasks; foreign screen;
repeated resolved read; cleanup first-throw retry; no dispatch after uncertain.
Add typed wrong-family/version failures and singleton descriptor tampering.
Prove frozen engine rejects incorrect claimed model and potion slot replacement.
Wire/host test all item payload variants, exact receipt/result offer matching,
full inventory, index255, malformed collect grammar, and counters/history/lag.
Test identical successive relic payloads with different outer lineage succeed,
but an old lineage replay cannot cause a second dispatch. Parent/card replay
semantics must remain unchanged. Test mixed item→upgrade→transform→item, shared
four-child limit, later failure retention, lost accepted/terminal responses and
no retry. Actual native→core→wire→Python cases include unrelated/held-out potion
and relic callers, delayed Offer/Chosen completion, and mixed card/item events.
Root owns exact project/provenance closures and final reviewed acceptance.

## Native observation and ownership

Generic event v6 retains the accepted G5 card operations and adds exactly one direct potion or relic reward in an owned nonterminal ordinary rewards overlay. No event-name or option-key admission table. Generic action reservation is two-stage; already dispatched parent effects remain unverified on later failure.

Add exact observational hooks RewardsSet.Offer(), NRewardsScreen.ShowScreen(RewardsSet,bool,IRunState), private NRewardButton.GetReward(). Retain all fifteen G5 hooks. Originals always run; exact signature/visibility/static shape, exclusive owner patches, partial installation rollback and retryable owner-thread cleanup cover all eighteen. No invocation of these methods by the bridge, no arguments/results replacement or extra command execution.

Offer under the matching inherited G5 Parent scope binds one exact RewardsSet and returned Task; the corresponding screen-creation scope binds the same set, player/run and nonterminal screen. A visible overlay alone cannot authorize anything. One card or item request consumes the current parent's request slot. Reject duplicate/nested/foreign request/screen generations, active testSelector, linked rewards, unsupported reward kinds and any domain other than one authoritative reward. Visible count alone cannot prove singleton. Offer awaits GenerateWithoutOffering before ShowScreen. Bind the exact set and Offer invocation first, then snapshot the authoritative singleton Rewards list at ShowScreen entry. Never require the final reward domain at Offer entry. The Boolean comes from whether the associated room is a CombatRoom; ShowScreen stores it directly as _isTerminal. Require false and the retained logical event-room/run context. The method assigns the exact set/run, pushes the newly created screen and returns that exact screen. Four observed public getters are passive field reads. Do not access the private backing fields from bridge code.

Retain exact Reward/offer model/player/run/set/screen identities and current slot/index facts at admission. Read only passive proved public accessors. Parent option button authority ends at predispatch reservation; use the existing G5 logical context and opaque receipt after ordinary dispatch. Never reread a freed option button to establish ownership.

Use the actual frozen ItemV1Session with session nonce and surfaceOrdinal=1. The native adapter proves offered index, reward/model/key, player/run/context and exact public reward surface at publication and immediately before the sole collect action. Potion requires the frozen complete ordered inventory with one empty slot and sole null-to-exact-offered-model insertion. Relic claim remains exact ClaimedRelic plus SuccessfullySelected; no total relic inventory certification. No Reward.OnSelect/command calls; only exact native ForceClick once.

A dedicated collection dispatch ticket/AsyncLocal around that real ForceClick allows only exact owned NRewardButton.GetReward to bind its returned Task. Never adopt a latest armed button or late unowned task. The retained OnRelease body directly calls GetReward on the same button and schedules its returned Task; the GetReward state machine awaits synchronized reward selection before emitting its collected/skipped signal. Observe this synchronous invocation under the dedicated ticket and retain its returned Task; do not invoke GetReward yourself. The game-owned selection still executes normally. Retain domain model and context beyond screen/button destruction.

The wrapper privately latches the frozen item-local resolved value, continues exact pending/context/claim validation, and publishes it only after owned GetReward, Offer and Chosen tasks succeed and the exact rewards overlay has closed. Failed/canceled tasks, context loss, changed offer/potion inventory or model/claim mismatch stop without full child completion. No parent action while this gate is pending. No repeated retired control dereference while waiting. Offer success proves its own awaited BeginRewardsSet completion; this is independent of screen closure. The private synchronizer task is never read or invoked by the bridge. Requiring both the observed Offer task and exact screen closure avoids treating either fact alone as completion.

There is one total 256 postdispatch read budget for item-local reconciliation and continuation combined. A successful final read256 may resolve. Pending read256 stops; read257 must never capture native state. No task progress or local resolution resets the budget. Frozen item engine and hashing are unchanged. Card pending256/257 behavior is separately preserved.

Use typed item/card public values with explicit outer child kind and contract version. Completed item count is separate from completed card count; combined episodes remain at most4. An item earns one reconciled child action and one item completion only on first delivered fully gated resolved value matching the exact sole accepted collect/index/kind/key. Public last-parent-action effects can report item_effect_verified and resets per previous contract; cumulative counters survive later parent actions/failure.

Tests require actual native hooks/adapter through frozen core, codec and Python parser, multiple unrelated/held-out event identities, potion and relic, identical successive relic offers with distinct parent lineage, mixed item/upgrade/transform/item/Proceed, delayed collection/task/callback and freed controls, full belt, changed offer, extra hidden reward, linked/custom/terminal rejection, wrong task/ownership/generation, uncertain collect without retry, late mutations after local resolution, budget boundary256, terminal rereads, cumulative counter lag/cleanup failure and all retained card regression suites.

## Ownership and acceptance gates

A owns G6 core, wire, host, pure item tests, wire tests and host tests; its initial implementation may consume native completion fixtures. B owns native hooks, bindings, adapters, inert stubs and native fixtures after independent acceptance of this native contract and its exact metadata result. R owns independent native-to-Python integration and review. Root owns shared contract, projects, checker, provenance, documentation and final freeze. Native source composition and claims remain blocked until that dependency is accepted; fixture-backed consumer work cannot imply production native evidence.

Full acceptance requires independent source/contract review, focused suites, actual-native integration, compile-only production builds against pinned references, reproducible matching production artifacts, complete predecessor identity closure, and candidate then frozen aggregate gates. Record the exact contract/source/result identities in the G6 acceptance ledger. No target game or Godot assembly executes in offline checks; game-owned Harmony may execute only against inert stubs.

## Static evidence boundary

The single reviewed metadata-only capture is retained at
`/private/tmp/generic-item-target-a/stdout.bin`, SHA256
`3572bc4a8170ec1d2a60951fae2743cea4d00ea90cde0f0502ac0b8d32953605`.
It contains exactly seven bodies and one public/static testSelector field
declaration,338 instructions total, with empty stderr. The four getters have
exactly three instructions each: instance field load and return. No getters
invoke further code. Offer is public/instance Task; ShowScreen is public/static
and its Boolean directly sets the screen terminal flag. The source
[scope](research/PHASE_1_GENERIC_ITEM_SCOPE.md) and
[native findings](research/PHASE_1_GENERIC_ITEM_NATIVE_EVIDENCE.md) preserve
identities and precise claims. Unknown Offer filtering lambda bodies, generation
implementation, synchronizer internals and other callers were not inspected and
are not inferred; observing the proved ordinary creation path and actual task
completion is sufficient for this singleton family. No new target capture is
implied. Fixture evidence and eventual live evidence remain distinct.
