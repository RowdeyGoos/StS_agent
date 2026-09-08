# Generic event v4 — retained multi-upgrade mapping evidence

2026-09-08. Implements the accepted [v4 contract](../PHASE_1_GENERIC_EVENT_V4_CONTRACT.md).
This report uses retained metadata only. No new game assembly inspection,
execution, assets, profile, network or live operations were performed for this
functional increment. Build and fixture results are separate from native live evidence.

## Rehashed retained inputs

The following exact files remain under
`/private/tmp/card-selection-static-qfocay2o/outputs/`; each was rehashed against
`raw_output_hashes` in [the API selection](PHASE_1_CARD_SELECTION_API_SELECTION.json).
They bind the pinned sts2.dll SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Temporary evidence availability grants no inspection replay authority.

| Retained file | SHA256 |
| --- | --- |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen.ShowScreen.jsonl` | `223fa0f03f91a8c3947e0efccf0473850e834016149f65c2298402b3c0394515` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen._Ready.jsonl` | `db436203f3a761befea642f85665cf8baaa82c16b6c9abea1f2c87e42c427289` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen.CheckIfSelectionComplete.jsonl` | `52d23070deb7332a85a45cc1b1f9f3276b2ce30091347c8d8c0a4602c5d0abe4` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen.get_UseSingleSelection.jsonl` | `ae3ffa56deaf588e2c5a7e5331aa1e24930e57e1dd33f1628cb8ab1b278f47ba` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Cards.Holders.NCardHolder._GuiInput.jsonl` | `e80bf68f895c65cced0efe50fdbfbf918760bc94f54279cfbd5066071a23715d` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen.OnCardClicked.jsonl` | `01bf27c78e87361d13a7eb87550cafa44a4157ef035d01e522642b7ef3bbf3cb` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NDeckUpgradeSelectScreen.ConfirmSelection.jsonl` | `5ad78d1d31b22bedd7efc84086f4af21b26c3ff951075d831af4f031a5ada622` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Cards.Holders.NCardHolder.EmitPressed.jsonl` | `8ab5a66addcf091d575d085838ec4aec20f68aab726a76ee08c2cdcd86c55703` |

Two additional retained captures were rehashed:

- `/private/tmp/event-card-preview-capture-235342f6df5b4c1ba424a6aa/stdout.bin`,
  14,163 bytes, SHA256 `587b2ee8484f2e372fb317416c94f048e47833d2e35f984e6a75dc62850e0857`.
  Its historical runner rejected canonical serialization. The preserved bytes were
  independently reviewed as bounded diagnostic evidence; this report does not
  relabel that invocation successful.
- `/private/tmp/generic-removal-preview-v2-target-a/stdout.bin`,
  23,108 bytes, SHA256 `f9404d721c4ba8824938ee0684ccf7fe21a885eda974bc986b825b986a82cf56`.
  This accepted six-body capture establishes public preview-holder projection.

## Exact shared control and clone chain

`CardSelectCmd.FromDeckForUpgrade(Player,CardSelectorPrefs)` returns the selected
originals through the existing bound task. The screen creation API is
`NDeckUpgradeSelectScreen.ShowScreen(IReadOnlyList<CardModel>,CardSelectorPrefs,IRunState)`.
It retains the explicit run state and candidate originals. The existing whole-deck,
request, preference, callback and screen ownership checks continue to apply.

The protected virtual synchronous `NDeckUpgradeSelectScreen.OnCardClicked(CardModel)`
records the selected original and highlights it. `UseSingleSelection` is true
only when MaxSelect equals one. For greater counts, the callback opens its
multi-preview only when selected count equals MaxSelect (IL145–166). The retained
body does not establish an early minimum-count preview for variable upgrades.
Both manual preference values therefore bind exactly while fixed min=max2..8 is
the new admitted slice.

For each selected original, OnCardClicked clears its grid highlight (IL271),
loads the screen's run state (IL277), calls `ICardScope.CloneCard(original)`
(IL283), upgrades the returned clone (IL290), creates an NCard displaying that
clone (IL304), creates an NPreviewCardHolder from that NCard (IL319), and adds the
holder to the multi-preview Cards container (IL324). This is synchronous within
the exact callback. It is not a public PreviewSelection method or an async
state-machine scope.

The diagnostic capture contains the concrete public synchronous method
`RunState.CloneCard(CardModel) -> CardModel`: it calls
`AbstractModel.ClonePreservingMutability`, casts the result, registers that card
with the same run state and returns it. This method does not assign CloneOf.
`CardModel.CreateClone` performs a separate CloneOf assignment, but the multi
preview bypasses it. Accordingly the implementation observes exact arguments and
returned references from only this concrete RunState method, inside an owned
callback scope; it does not infer mapping from CloneOf, card keys or order.

The six-body capture proves `NPreviewCardHolder.Initialize` calls inherited
SetCard with its NCard argument, and `NCardHolder.SetCard` retains that exact node.
`NCard.Model` returns the displayed model. The actual public holder/card/model
chain can therefore be matched to the observed clone, then to its captured
original. No private field reads are needed. Multi `_Ready` binds
`%UpgradeMultiPreviewContainer`, `Cards`, and `Confirm`; ConfirmSelection invokes
CheckIfSelectionComplete, which resolves the original selection task and removes
the overlay when selected count reaches max.

## Deferred dispatch and bounded ownership

The retained `NCardHolder._GuiInput(InputEvent)` calls Godot CallDeferred for
EmitPressed (IL65). EmitPressed emits the holder's signal with that exact holder.
An AsyncLocal scope around _GuiInput therefore cannot establish the callback
lineage by itself. Before native dispatch, the new adapter reserves one ticket
for the bound screen, original and retained holder. The ticket's validator
recaptures exact grid, geometry, holder, card, hitbox, highlight and material
identities, plus visibility/enabled and unselected state when the callback begins.
The callback consumes this ticket once on its owner thread; callbacks never create
authorization. No second selection is exposed while it remains outstanding.

A synchronous thread-local scope then observes only the exact concrete RunState
clone calls. Each returned clone must be unique and disjoint from the entire
baseline deck and candidate original domain. A parent-adapter-owned identity set,
bounded at four episodes times eight clones, also rejects reuse by a later child. The final complete mapping must
cover the exact selected set. Holder/card/clone identities are retained after the
first complete preview, including each holder's clone assignment, so replacement
or swapping known clones fails before Confirm. An initially partial display may
wait for the already completed mapping's remaining holders; a bound complete
display cannot later lose members.

This is correlation under the accepted single-controller ordering contract.
Indistinguishable callbacks for the same pending holder do not carry an
unforgeable queue token. Nonpreview clone calls confer no authority. Existing
single-upgrade, removal and reward adapters retain their predecessor behavior;
only the new multi-upgrade adapter uses typed live hitboxes with exact retained
references, matching the accepted reward repair.

Selector and request result enumeration is bounded at admitted max+1. Both exact
original result sets, successful Chosen completion and native selector closure
remain required. Frozen card reconciliation verifies ordered deck originals and
keys, exactly one upgrade on selected originals, no other delta and monotone
partial progress. It does not certify other event effects. Transformation remains
unsupported: its replacement-pair and randomness boundaries need separate evidence.

## Offline implementation evidence

The first completed focused snapshot `/private/tmp/generic-v4-b-03` compiled both
the inert native fixture and the compile-only pinned native adapter with zero
warnings/errors. It passed 1,289 assertions, explicitly checking that the first
745 preserved predecessor assertions ran before new multi-upgrade cases.
New native cases include fixed2 and8, both manual preferences, three unrelated
inert EventModel subclasses, reverse selection, deferred creation/click/preview/
completion, partial upgrades, clone and control mutation rejection, exact effect
rejection and lost Confirm without retry. Installation rollback is exercised at
each of the nine targets. Additional final integration, review, freeze and
aggregate evidence belongs in the acceptance ledger; this report makes no new
live success claim.

## Deferred transformation boundary

The retained public request signature is
`CardSelectCmd.FromDeckForTransformation(Player,CardSelectorPrefs,Func<CardModel,CardTransformation>)`
returning `Task<IEnumerable<CardModel>>`, with attributed state machine
`<FromDeckForTransformation>d__19`. Its wrapper/state-machine body is not part of
this increment's retained inspected bodies. The screen API is
`NDeckTransformSelectScreen.ShowScreen(IReadOnlyList<CardModel>,Func<CardModel,CardTransformation>,CardSelectorPrefs)`.
Its retained OnCardClicked/OpenPreviewScreen path selects originals and projects
them through the supplied transformation function before `NTransformPreview.Initialize`.
The function must never be invoked by the bridge merely to discover a replacement.

Retained CardTransformation declarations expose Original, Replacement,
ReplacementOptions and GetReplacement(Rng). Declarations alone do not prove the
final replacement selected after randomness and native hooks. Retained CardCmd
signatures include `Transform(CardModel,CardModel,CardPreviewStyle)` returning
`Task<CardPileAddResult?>`, and
`Transform(IEnumerable<CardTransformation>,Rng,CardPreviewStyle)` returning
`Task<IEnumerable<CardPileAddResult>>`, with state machines d__11 and d__13.
Their bodies and the NTransformPreview public preview mapping have not been
established by this multi-upgrade work.

A future separately reviewed minimal metadata scope should first establish those
exact Transform request/command boundaries and NTransformPreview's public mapping
and commit controls. It should capture only explicitly selected bodies and needed
member declarations, preserving pinned hash/size limits and no recursive following.
The frozen card core additionally requires unchanged deck length, replacements at
each original's exact position, and unchanged unselected originals. No proposed
transformation family should be implemented until an authoritative original-to-final
replacement mapping and that positional effect contract are proved compatible.
No new scanner, target read or execution is authorized or performed by this report.
