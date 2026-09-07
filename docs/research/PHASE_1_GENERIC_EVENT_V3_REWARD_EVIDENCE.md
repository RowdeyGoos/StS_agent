# Generic event v3 — retained reward selection evidence

2026-09-07. Read-only audit of retained, hash-bound metadata outputs for the
[v3 contract](../PHASE_1_GENERIC_EVENT_V3_CONTRACT.md). No new target inspection,
assembly execution, live operation, profile access or network operation was
performed. This evidence establishes the shared request/screen family; event
names remain fixture identities and are not native admission policy.

## Retained source and verified identities

Files below are under `/private/tmp/card-selection-static-qfocay2o/outputs/`.
Their exact bytes were rehashed against `raw_output_hashes` in
[the retained API selection](PHASE_1_CARD_SELECTION_API_SELECTION.json).
All bind the original pinned sts2.dll SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Temporary output availability does not authorize reconstruction or replay.

| File | SHA256 |
| --- | --- |
| `sts2.members.MegaCrit.Sts2.Core.Commands.CardSelectCmd.jsonl` | `d3daf5216cc1e33cf086a79b907f1196805acb267636ed56dc1bebc8d2b34195` |
| `sts2.il.MegaCrit.Sts2.Core.Commands.CardSelectCmd_<FromSimpleGridForRewards>d__14.MoveNext.jsonl` | `55430a85b4eb807da994d62ed556a021997d3d718fd8a3f150870e322e5f08e1` |
| `sts2.members.MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult.jsonl` | `f01ff4c9efc11121ae55f4709f39a2c672a57156238603578c2ee860051fcaa5` |
| `sts2.il.MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult.get_Card.jsonl` | `61b55217faa59d531f13cee98f307618ea78aeb0ef65edb280c61a26393fd40a` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen.Create.jsonl` | `0da827795be67a54dbaa40438bcb55dceff84e25e1cae03aca259e9ddf54b4b9` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen_<>c.<Create>b__13_1.jsonl` | `71e4bb7ef9bdcc8898673ddb7aa1cb9fa80fa173db80a6aec9c003c4bc95af5f` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen._Ready.jsonl` | `22edc8b8777d29124439edb8ec36b519c04fe16ebc04aa3a12ba4f24fa1ac9ec` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen.OnCardClicked.jsonl` | `3a9fcfa7ed4e24bb6bde70389f926b4bf5ea0b5a538c849533491dd0f6aa67e6` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen.CheckIfSelectionComplete.jsonl` | `c6a953a12c010010414368ba07735a9403032ec41f519b1abc22035b238e9676` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen.CompleteSelection.jsonl` | `4b2f353d1144b1486a5983782fb434d941d39f57cb33a05952d016804adfd34d` |
| `sts2.il.MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NSimpleCardSelectScreen.<_Ready>b__14_0.jsonl` | `0ae163648fdadffe854094cd99e231ca3c0e7d0c69f105aaa58118134d7e7dfa` |
| `sts2.il.MegaCrit.Sts2.Core.Factories.CardFactory.CreateForReward.jsonl` | `a96da23e624878f50e61148a178ff4878685df7220c6adb9387f72556488a34b` |
| `sts2.members.MegaCrit.Sts2.Core.Commands.CardPileCmd.jsonl` | `23f29930b6e7b5e2641e18f4cffd0af38316d2ff6112618252d6d566bb2c892d` |
| `sts2.il.MegaCrit.Sts2.Core.Commands.CardPileCmd_<Add>d__9.MoveNext.jsonl` | `1e68df66e03686328d02b088be0c57a848af578587353aab5bc872d0c917dc35` |

## Request, ownership and offer provenance

The exact public static method is
`CardSelectCmd.FromSimpleGridForRewards(PlayerChoiceContext,
List<CardCreationResult>, Player, CardSelectorPrefs)`, returning
`Task<IEnumerable<CardModel>>`. Its attributed state-machine body reserves a
choice id for the explicit Player at IL437, awaits the supplied context's
SignalPlayerChoiceBegun at IL454, and selects the local branch using that Player.
The local branch calls the CardCreationResult overload of
`NSimpleCardSelectScreen.Create(IReadOnlyList<CardCreationResult>,CardSelectorPrefs)`
at IL580, pushes that screen at IL594, and awaits its CardsSelected task at IL601.
It later awaits SignalPlayerChoiceEnded at IL950 before returning its selected
CardModel list. Empty/ending and nonmanual count<=min shortcuts create no selector.
The v3 domain>max bound deliberately excludes those shortcut paths.

PlayerChoiceContext is an opaque identity. No retained owner property is assumed.
The already hash-bound callback diagnostic
`/private/tmp/event-card-callbacks-capture-08be47c191934886a0103cd5/result.json`
(246733 bytes, SHA256
`e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`)
contains an example caller constructing BlockingPlayerChoiceContext with no
arguments and passing EventModel.Owner separately. The generic ownership witness
is the exact Player argument plus inherited Chosen/request/creation causality.

CardCreationResult is a reference class. Its public Card getter returns
`_modifiedCard ?? originalCard`; reward hooks may replace the effective offer.
V3 therefore snapshots each unique result entry and its effective current Card,
not a presumed unmodified generation result. Native creation copies the result
list, optionally sorts the copy through prefs.Comparison, and projects each
entry's Card getter into the screen's candidate list. Actual displayed holders
establish slot order; their card references must form the complete offer set.
Request-list identity/order, entry identity, effective card identity/key/level,
owner/run state and all rule-bearing preferences must remain bound across
creation and child control. Disjointness is checked against the original
baseline deck, allowing selected offers to enter the current deck on submission.

## Native modes and completion boundary

For nonmanual selection, OnCardClicked highlights and records the clicked original,
then calls CheckIfSelectionComplete at IL104. That method calls CompleteSelection
when selected count reaches max. With positive min the Confirm button starts
disabled; subsequent clicks enable it only when both count>=min and manual
confirmation is required. Thus nonmanual min<max retains meaningful min metadata
but offers no early commit. Final select commits at exactly max, with no preview.

For manual selection, the native Confirm button becomes enabled at min and its
released callback directly invokes CompleteSelection. It supports any accepted
count through max and does not auto-submit at max. CompleteSelection sets the
selection task result to the original-card set at IL12 and removes the overlay
at IL23. Neither mode uses an original-to-clone preview mapping.

The reward request returns selections and does not itself add cards. CardFactory
may modify reward options before the request; CardPileCmd.Add may prevent or
modify additions through its hooks. V3 admits only the observed outcome where
all selected exact originals enter the deck without any other deck delta, as
proved by the actual frozen CardSelectionV1Session. Exact request/selector sets,
successful Chosen/request tasks, selector closure, and monotonic partial-add
reconciliation remain mandatory. Altered/prevented additions stop or exhaust the
bounded wait; they are not silently relabeled successful.

No separate CardPileCmd.Add task is intercepted, and this evidence does not
certify completion of all add hooks/animations, other event effects, or a global
event-state postcondition. Real EventSynchronizer scope preservation remains a
live gate. Build/test evidence for the new implementation belongs in its
acceptance ledger, separately from these retained static facts.
