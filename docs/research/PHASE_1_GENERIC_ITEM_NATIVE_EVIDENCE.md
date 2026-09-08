# Generic singleton item native evidence

2026-09-08. Read-only interpretation of the single reviewed item metadata capture.
This supports the bounded G6 native implementation contract; it does not establish
live behavior, install a release, or change any of the 25 frozen predecessors.

## Exact evidence

The accepted scope is `PHASE_1_GENERIC_ITEM_SCOPE.md`, SHA256
`d659a93c6a21161dc7fe94e11964a4037440d1a69b190f472b42ac93e273e411`.
Root performed the sole reviewed capture into `/private/tmp/generic-item-target-a`.
The retained `stdout.bin` was independently rehashed before interpretation:
SHA256 `3572bc4a8170ec1d2a60951fae2743cea4d00ea90cde0f0502ac0b8d32953605`.
It contains exactly seven bodies, one field declaration and 338 instructions;
stderr is empty. The target is the pinned 9,363,456-byte sts2.dll with SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No target invocation, assembly load, dependency resolution or extra target read
was performed during this interpretation.

The corrected toolset at `/private/tmp/generic-item-inspector-a` passed 58 inert
checks and independent review. Source manifest SHA256
`fc32cc71d3637a1736c8f003ad24a111e14b4d927085bdd40819f09ca3d72675`;
three-file bundle manifest
`9cd165d9a67f0e1ddae8f49795e4980bb80eb7132f6715d32ac8b954d7459b3d`;
synthetic manifest
`38923524cf056ed4b2fc995f870f8469b115ac0e83c97d7c719d336dbe345788`.
The initial reviewed toolset remains in its `prior-reviewed-a` directory.

## Passive public ownership accessors

All four selected getters have precisely `ldarg.0`, `ldfld`, `ret` (three
instructions each). They are public instance HideBySig/SpecialName methods:

- `RewardsSet.Player` returns its Player backing field.
- `RewardsSet.Rewards` returns its `List<Reward>` backing field.
- `RewardsSet.DisallowSkipping` returns its Boolean `_disallowSkipping` field.
- `Reward.ParentRewardSet` returns its LinkedRewardSet backing field.

Their getters perform no additional invocation. Native observation can use these
public getters; the bridge need not read their private fields. The selected
`RewardsSet.testSelector` declaration is public static
`Func<RewardsSet,Task>`. No field value was projected by the metadata reader.
Future native admission can reject a nonnull public selector without invoking it.

## Request, generation and exact screen creation

`RewardsSet.Offer()` is a public instance method returning Task. Its small body
constructs an async state machine and returns that invocation's builder Task.
The selected private generated `<Offer>d__33.MoveNext()` shows:

1. A dead-player branch can return without screen creation (IL36–54).
2. It calls and awaits `GenerateWithoutOffering` before proceeding (IL60–148).
   Therefore an Offer-prefix list snapshot cannot define the final offered domain.
   Reserve the exact set/player at Offer entry; bind the actual authoritative
   singleton list/reward at the owned ShowScreen entry after generation.
3. It computes `Room is CombatRoom` into the Boolean local at IL153–167 and
   obtains a Task from `RewardsSetSynchronizer.BeginRewardsSet(this)` at
   IL170–181. An empty noncombat/non-allow-empty branch can return early.
4. The ordinary local, non-test path calls ShowScreen at IL675–688 with this
   exact set, the computed Boolean and this set's player's RunState.
   Remote/test/custom branches can omit the screen. Their mere presence does
   not authorize adoption of some later foreground screen.
5. It awaits the retained BeginRewardsSet Task at IL694–780 before successful
   Offer completion. This is separate from observing UI closure.

`NRewardsScreen.ShowScreen(RewardsSet,bool,IRunState)` is public static and
returns NRewardsScreen. It instantiates a screen, stores its exact first argument
as `_rewardsSet` (IL25), the Boolean as `_isTerminal` (IL32), and the run state as
`_runState` (IL39), pushes this screen onto NOverlayStack (IL44–50), and returns
that same instance (IL55–56). Thus a prefix/postfix observer can prove the public
argument-to-return identity association without private-field access.

The first supported item family admits only the observed Boolean false, exactly
one direct supported reward in the authoritative list, and an exact owned
ordinary screen. The count is not inferred from visible controls. Generation may
be deferred; synchronous creation must be buffered until the returned Offer and
Chosen Tasks have both been bound. No-screen completion is unsupported.

## Existing button and closure evidence

The following previously approved files under `/private/tmp/sts-mr-api-v47tiwjy`
were rehashed against the repository's missing-room API selection:

| Retained file | SHA256 |
| --- | --- |
| NRewardButton--OnRelease.il.jsonl | `209b697ca6aaa33c1f388c4b33154ceefea0070b024540d413315c6b8a3fed72` |
| NRewardButton+\<GetReward\>d__26--MoveNext.il.jsonl | `027317330c69eafb6c400b9178b6e34168ad9b89845ea01e399aef4921a59d2c` |
| NRewardsScreen--UpdateScreenState.il.jsonl | `8646c7cba87728b9e92140c82dfdf63f17c10d5b33461a3738a98813c49cf6f8` |

OnRelease directly calls its own GetReward at IL13, then passes the returned
Task to TaskHelper.RunSafely at IL18. The retained GetReward state machine awaits
synchronized reward selection, then emits RewardClaimed on success or restores
the skipped path. The bridge still invokes only the native button's ForceClick.
A fresh dispatch ticket and inherited invocation scope must observe the exact
button's GetReward entry and returned Task. No global latest-button fallback,
foreign invocation or direct GetReward call can supply that authority. If the
actual ForceClick path does not produce the expected owned invocation, fail
closed rather than infer dispatch completion.

UpdateScreenState's empty nonterminal branch removes the screen from the overlay
at IL235–242. The terminal branch instead marks completion and emits Completed,
retaining the terminal Proceed flow. The new contract therefore requires both
actual nonterminal screen closure and successful exact Collection/GetReward,
Offer and Chosen Tasks. No completion is inferred from having collected the only
visible control. Retired screen/button references remain opaque receipts while
pending; exact logical parent, run/player, reward/model and inventory facts stay
observable without dereferencing freed native controls.

## Resulting contract and limits

Reuse the actual frozen ItemV1Session for one direct potion or relic collection.
Potion proves the unchanged ordered inventory plus one empty-to-exact-offered
model insertion. Relic retains the existing reward-local proof of exact
ClaimedRelic plus SuccessfullySelected; no total relic-count or arbitrary hook
semantics are inferred. Linked rewards, multi-offer sets, full potion inventory,
unsupported kinds, terminal/custom/test/selectorless and foreign-generation
paths are excluded. These are generic request/surface predicates with no event
name or option-key allowlist.

A cached local item resolution does not end native reconciliation. Continue
fresh claim/inventory and ownership checks until all exact tasks and closure
conditions hold, within one shared 256-read post-dispatch budget. Task identity
must remain stable within each role of an episode. Distinct owned invocations
may return the same cached completed Task in different roles or later item
children; invocation/ticket plus fresh set/screen/reward generation provides
ownership, rather than a global item Task-uniqueness restriction. Existing card
Task rules remain unchanged.

The captured Offer lambdas, GenerateWithoutOffering and synchronizer helpers
were not recursively inspected. Their internal predicates, generation algorithm
and completion bookkeeping are not claimed here. Admission observes the actual
generated singleton at the exact owned screen boundary and requires the actual
returned tasks to succeed, so this narrow contract does not need to infer those
internal implementations. No additional metadata read is selected.
