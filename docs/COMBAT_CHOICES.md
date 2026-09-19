# Combat card choices

The single bridge can resolve the pinned game's public discard/exhaust grid
selector while a combat card is pending. `components/cards/combat/` owns the
protocol and reconciliation; `combat_native/` binds the actual screen;
`apps/bridge/client/combat_host.py` owns bounded host control. This is separate
from generic event card effects. See [bridge commands](../bridge/Sts2AgentBridge/README.md)
for release and installation usage.

## Native scope

The representative caller is **Neow's Fury**. Metadata-only inspection of pinned
`sts2.dll` SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`
shows `NeowsFury.OnPlay` calling `CardSelectCmd.FromCombatPile` on the discard pile
with a zero minimum, then adding the returned cards to hand. The native path uses
`NCombatPileCardSelectScreen`, its selected-card set and inherited completion task.
No game assembly was executed for that inspection.

Supported screens have 1–64 allocated, distinct public card holders, a maximum
selection of 1–8 and a minimum of 0–maximum. Bounds are clamped to the displayed
domain as in native code. The adapter preserves the native manual-confirmation
setting and actual enabled confirm button. Optional zero uses a native confirm;
it is not cancellation. Fixed and variable counts use the same surface.

Every read and dispatch checks the bound run, combat, single player, overlay,
pile, controls, holder/model/node identities, public keys/upgrades and ownership.
Draw, hand, deck, custom selector classes, changed domains, external selection
and cancellation are unsupported. No draw order, game RNG, selector override,
profile or save data is read. Eligible allocated off-screen holders use the same
native input path; this has fixture coverage, not a new live off-screen result.

`NCardHolder._GuiInput` checks `_isClickable` and defers `EmitPressed` for the
select action. The adapter checks that native gate as well as visibility and the
hitbox's enabled state. It dispatches once to the bound holder, then waits for the
exact selected-set change. Final automatic selection and explicit confirmation
remain pending until the original native task succeeds with the exact unique
model set and the overlay closes. Successful disposal releases the child owner.
It does not by itself certify the card's later gameplay effects.

## Interface and ownership

Authenticated shared-listener routes are:

- `GET /probe/combat-choice-v1/public/decision`
- `POST /probe/combat-choice-v1/public/action`

Bodies use `schema_version: 1`, `protocol: combat_card_choice_v1`. The shared
client encodes the POST's `decision_id` and `action_id` in the existing bounded
transport grammar. A ready observation supplies a stable episode `choice_id`,
a fresh legal-state `decision_id`, pile, min/max, manual-confirmation flag,
public candidates (`slot`, `key`, `upgrade_level`, `selected`, `enabled`),
`selected_slots`, `legal_actions` and attempted/accepted/reconciled counts.
Actions are `select:N`, `deselect:N` and `confirm`, only when advertised.

Waiting observations expose no candidates, legal actions or decision ID. Complete
observations report the selected slots and `selection_verified`; the next read
may discover a new selector or report idle waiting. Accepted receipts echo the
choice/decision/action identities and counts. Failed responses contain a bounded
code and counts, never native exception text. Uncertain dispatch, duplicate/stale
input, changed identity, mismatched result or failed disposal stops the host.
There is no mutation retry or adoption of an uncertain prior action.

The child can run inside a pending core combat action. It fences all other
ordinary core gameplay and feature modules while active. Child completion leaves
the original combat action pending until a changed combat decision or terminal
combat result separately reconciles it. Metadata remains readable. A pending
noncombat core action cannot start this child.

Native limits are 32 selector episodes per process, 2,048 reads per episode,
200 pending reconciliation reads and 32 attempted inputs. Shared transport and
core limits also apply.

<a id="host-behavior-and-validation"></a>

## Host behavior

`--capability combat-choice` resolves one selector. `--capability combat` uses the
existing public combat codec and heuristic provider, resolves a supported chooser
when combat waits, then resumes the same combat. `--choice-policy first-select`
selects available cards up to the maximum; `minimum` confirms as soon as native
controls permit it. The Python chooser provider is replaceable and receives an
immutable observation. These are mechanical policies, not strategic-quality claims.

The host limits each selector to 30 seconds, 2,048 reads and 32 actions, within a
combat limit of 300 seconds, 4,096 reads, 48 accepted/72 attempted combat actions,
24 known no-mutation stale rejections, 12 rounds and 32 child episodes. Bounded
in-flight transport may finish after a deadline; a late response cannot pass.
All exits retain attempted, accepted and reconciled combat counts and completed
child summaries. Only the exact native `queued` receipt counts as accepted;
a later observation establishes reconciliation. After a queued end-turn, changed
observations in the original round remain pending and service native choices;
only the exact next round or terminal combat reconciles that end-turn. Backward
and skipped rounds still stop. Unknown/lost receipts stop.

The shared `combat-map` mode composes this combat controller with the maintained
reward codec, then the existing map-readiness check. It claims gold, chooses or
skips supported card rewards and stops at an actionable map. Each stage retains
its own evidence; defeat prevents reward control and reward failure prevents the
map check. The new reward host uses stable reward-set indices through compacted
visible slots, binds opened card children to their original offer, checks player
and revision transitions and never counts an unverified receipt as an effect.
See the [bridge guide](../bridge/Sts2AgentBridge/README.md#installation-client-and-cleanup)
for policy flags, bounds and shared-client pacing.

## Evidence

[Status](STATUS.md) owns current support and remaining live gaps. The
[September 9 ledger](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) records Neow’s Fury
zero/two-card selection, resumed victories and both terminal card policies through
an actionable map, with original release identities and earlier failed attempts.
Other exhaust/fixed-count callers retain fixture coverage; this does not establish
full-run play. [Current release validation](../bridge/Sts2AgentBridge/releases/current/README.md)
binds the integrated checks.
