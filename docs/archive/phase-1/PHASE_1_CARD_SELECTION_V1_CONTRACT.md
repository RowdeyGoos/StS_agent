# Card selection v1 contract — accepted for core slice

Date 2026-09-06. New isolated sibling:
`bridge/Sts2AgentBridge/successors/card_selection_v1`. All nine predecessors and
old 0.8.0 remain frozen. User request: event add/transform/upgrade/remove, including
multiple cards; ordinary rest smith upgrades exactly one. This contract is a
shared engine for those operations, not a claim that every event is identified.

## Authority and initial native entries

A successor-owned immutable parent context binds session nonce, parent kind
(event/rest), parent decision/action receipt, run/player/room/map references,
exact parent option/controller, operation, cardinality and commit mode. A child
is admitted only as the first foreground transition after that accepted parent
receipt. No existing selector may be adopted at startup or after an uncertain
parent action. Parent identities never appear on the wire.

Production policies are exact statically witnessed callsites. Initial entries:
RoomFullOfCheese GORGE -> NSimpleCardSelectScreen, add, min=max=2, auto on final
selection, eight offered cards; SmithRestSiteOption with SmithCount==1 ->
NDeckUpgradeSelectScreen, upgrade, min=max=1, single-preview confirmation.
Unknown callsites fail unsupported. Generic fixture adapters can exercise all
four operations and multi-card event upgrade/remove/transform; that evidence does
not enable unproven production parents. Later policies need the same static gate.
Do not infer operation/count from localized labels or button enablement. Rest
rejects any operation other than upgrade, or cardinality other than exactly one.

## Public and native values

Pure core has no game/Godot dependencies. Native identities are opaque tokens:
the core only uses reference equality and never inspects target objects or emits
them in public/wire values. Immutable copies throughout. Initial admission must
observe an empty selected set, an incomplete retained selection task, and no
preview. A synchronously completed/canceled/faulted task at admission rejects
before dispatch; there is no adoption of preselected results. Native
adapter captures exact parent/run/player/screen binding, a bounded candidate
list (max 64 cards covering the complete authorized domain), complete before/current deck (max 512) with an explicit `CompleteDeck` witness, current
phase and exact control bindings. Candidates have index, stable definition key
(max128 ASCII approved key alphabet), retained holder and model references,
upgrade level, visible/enabled and selected state. Duplicate definition keys
are legal at distinct slots; duplicate model/holder refs are not. For Cheese the complete domain must be exactly eight unique offered refs with
visible bound holders. For Smith, the parent-proven eligible deck projection
must match the complete visible grid one-to-one, with no hidden/offscreen
eligible card, paging/filtering ambiguity or overflow. A partial visible page is
unsupported in v1; scrolling is a later capability. Candidate
slots/order and refs remain fixed for the child; redraw/paging/replacement stops.

Policy min/max are 1..8 with min<=max. Commit mode is auto_at_max,
explicit_confirm, or preview_confirm; preview_confirm has a separate optional
open-preview control for range selection, and a final confirmation control.
Production v1 entries use only exact cardinality. Capture phases are selecting,
preview, submitted, or transient. Preview captures provide exact selected
original refs through publicly bound preview models where available; otherwise
only a statically proven final-selection-to-preview transition with unchanged
retained candidates and reserved prefix may proceed, and final task result must
still exactly match the reservation set before any effect is claimed.

The selected native grid's public CardsSelected() is called exactly once when
admitted. Audited body merely awaits the existing completion source; no target
mutation. Retain the task, never block an owner thread, snapshot its result once
on successful completion. It yields selected ORIGINAL model references, not a
deck-effect receipt. Canceled/faulted task is terminal. Success may precede
actual overlay removal; wait for both. Do not invoke this method on a screen
that failed parent admission.

Public grid highlight is selected-membership evidence only after exact mapping
and animation endpoints are established. Intermediate animation means transient,
never ready. No private prefs, selected collections or reflection. Labels are
observational text only. Card dispatch is retained holder._GuiInput with one
fresh select/pressed InputEventAction, disposed in finally; it preserves native
clickability guards and is deferred. Confirm dispatch uses the exact revalidated
retained visible/enabled control's previously proven ForceClick route. No direct
signal emission that bypasses native guards, private method or card command.

## Session and action semantics

One owner thread; reject reentry; disposal latches failure. Read/Apply capture on
owner thread. Every ready decision is canonical and bound to policy, parent,
phase, immutable candidates/selected prefix and legal actions. Select action is
`select:<slot>` only for a visible enabled unselected candidate while selecting
and count<max. No deselect, cancel, skip or scroll. `preview` is legal only when
min<=count<=max, mode preview_confirm, and an exact enabled preview control is
present. `confirm` is legal only in the correct mode/phase with cardinality met
and an exact enabled final control. Never publish confirm after the first card
of an exact-two policy.

Apply must recapture and compare full public projection and all retained native
bindings. Reserve decision/action and expected selected set BEFORE one dispatch.
Only one mutation is pending; no replay or repeat decision/action. A throw is
uncertain terminal with reservation retained. A-B-A, foreign selection, changed
policy/count/holder/control/parent, malformed result and unexpected deck delta
are terminal; later matching state cannot be adopted. No retry after timeout.

A nonfinal select resolves only when exactly the requested new selected card
is observed alongside the prior correlated prefix, with no other candidate
change or deck effect. At max, an audited auto mode may publish its exact task
result without an intermediate highlight; preview mode may open its bound
preview. Neither case means the parent effect is complete. Receipt histories
remain immutable and correlated in later observations/results. Pending reads
are bounded at 256 per mutation; total accepted mutations <=10 (8 selects,
optional preview, confirm). Every terminal state is stable.

## Effect reconciliation and parent continuation

Every admission, recapture and reconciliation requires `CompleteDeck=true`; a
bounded list without proof of full public deck enumeration is insufficient.
Native code sets this only after a full bounded, deduplicated public deck copy.

Final commit requires the retained task's exact unordered selected reference set,
no additional/duplicate refs, closed bound selector, unchanged parent identity,
an operation-specific complete deck witness, and a typed
`EffectCompletionObserved` witness after the native caller finishes its awaited
work. Cheese uses the exact retained event's `IsFinished`; Smith uses restored
Proceed with travel enabled, map still closed and nontraveling. A deck change
can precede after-hooks and cannot alone set this flag. Until then, only admissible
monotonic prefixes of the exact effect may remain pending:

- add: selected offered original refs appear once each in the deck; all before
  refs/keys/upgrade levels and their relative order remain unchanged; no other
  additions. Callsite must prove originals are passed to the add operation.
- remove: only selected original refs disappear; all remaining cards retain
  refs/keys/upgrade levels and relative order.
- upgrade: same complete deck refs/order/keys; exactly selected originals each
  increase upgrade level by one, and all others remain unchanged.
- transform: selected originals disappear and are replaced by a result-bound
  replacement reference per original; replacement witnesses must be supplied by
  an independently proven native completion path, never guessed from deck count
  or predicted from RNG. Original/replacement refs distinct and no unrelated
  change. Without that witness, native transform stays unsupported.

Gold/HP or other effects are not inferred. Empty deck changes or selector closure
alone cannot resolve. Selection-confirmed and effect-reconciled are distinct.
After child resolution, event waits for a changed structural parent projection;
rest waits for its restored controls. Each requires a separate accepted Proceed
and same-map open/travel-enabled/nontraveling witness to finish the parent.
Frozen item children remain separate and are not widened into card selectors.

## Packet ownership and gates

Coordinator owns this contract, static evidence, aggregate integration gate,
source identities and documentation. A owns core/tests and wire/host with their
fixtures. R owns the pure parent session, parent fixtures and actual parent-adapter
source tests against inert target stubs. B owns the native
selector and native parent adapters and their compile/fixture seams. Reviews
cross ownership: R reviews core/native; A reviews parent; coordinator reviews
wire/native-parent and integrates. No shared write ownership.

Required fixtures: event all four modes at count1 and count2, two-of-eight with
no early confirmation, exact-one rest and invalid rest count/mode; explicit,
auto and preview completion; duplicate keys; stale/foreign/redraw/cardinality
changes; uncertain kth dispatch with prefix retained; completion-before-removal;
wrong/canceled task, partial/excess/foreign effect, transform replacement binding;
immutable output/canonical identity, bounds/reentry/disposal/no later adoption;
parent-child correlation and separate Proceed/map. Native compilation is not
live evidence. Production transport, artifact verification, packaging and a live campaign
remain later gates.

## Independent contract disposition

Review accepted the core slice after empty-selection/incomplete-task admission
and complete-domain projection were made explicit. Include synchronous task
completion-at-admission, hidden eligible card, partial page and overflow fixtures.
Native implementation remains gated on the final exact member/passivity mapping
report; abstract fixtures do not authorize production policies.

## Parent and wire composition

The pure parent session supports one exact Cheese Gorge or ordinary Smith entry.
It accepts at most two parent actions: begin and Proceed. After accepted begin it
admits the first exact sole foreground child screen, creates the real core child
from the same parent context, and checks that every available child capture keeps
that screen identity. It never adopts an initially open selector. Child completion
is necessary before the separate restored parent Proceed; final result requires
the bound map open, travel enabled and not traveling. Native transition waits
are finite. Stable control delegates and structural witnesses are revalidated
before reserve-and-dispatch.

The reviewed `wire/schema.md` specifies four exact in-process routes and canonical
UTF-8 scalar-only JSON. POST is exactly decision_id/action_id, at most 256 bytes;
responses are at most 65536 bytes. The Python 3.10+ host takes injected transport
and a monotonic clock, keeps a 30-second deadline, at most 1024 GET and 12 POST
attempts, and stops without retry after any uncertain transport/action outcome.
Both service and host validate receipts, exact selection cardinality, monotonic
child action histories and final begin/Proceed correlation. This development
component has no listener, socket, operator credentials or live campaign CLI.
Those remain production composition and release-verification work.
