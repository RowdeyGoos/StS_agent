# Shuffle and generated-entry hooks — 2026-09-14

Scope: solo Ironclad, Ascension 0, Overgrowth Act 1, pinned 0.107.1 / Steam
23811903. Assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

## Native evidence and boundaries

Pinned method inspection establishes the command recipe and listener order:

- `CardPileCmd.Shuffle` state machine `100712243` starts with discard, appends
  existing draw enumeration, uses StableShuffle, repopulates top-first, then
  awaits AfterShuffle. Bottled Potential first adds its hand at Bottom (enum 1).
- `Hook.AfterShuffle` state machine `100711477` awaits each listener.
  CombatState enumerates creature powers before player relics: Stratagem resolves
  before The Abacus grants six unpowered block.
- `CardSelectCmd.FromCombatPile` state machine `100712298` bypasses sorting when
  all available cards are automatically selected. Required selectors use stable
  rarity/model-ID ordering; native Quest rarity is 10, after Curse 9.
- Opening `Player.PopulateCombatState` `100696112` calls
  `CardPile.RandomizeOrderInternal` `100696519`: UnstableShuffle and initial
  ModifyShuffleOrder, with no AfterShuffle. SetupPlayerTurn `100712569` applies
  draw modifiers before repeated Innate MoveToTop, then raises the count to the
  number of Innate cards, capped at ten.
- Stomp `AfterCardEnteredCombat` `100693376` skips clones and counts only finished
  owner Attack plays this turn (`100693379`). BeforeCardPlayed `100693377`
  discounts existing listening instances for each owner attack iteration;
  ReduceCostBy `100693378` adds a turn modifier. Offered cards are not listeners.

The retained [native shuffle vectors](../../tests/fixtures/headless_native_combat_vectors.json)
and [oracle](../../tools/native_combat_oracle/README.md) remain unchanged. This
batch reuses all 24 actual StableShuffle records (three seeds, sizes
0/1/3/10/16/17/31/64) with input copies assigned across discard, draw and hand in
the source-established merge recipe. Expected permutations and RNG suffixes
still come from the native assembly. Innate arrangement, full command execution,
hook sequencing and cost continuations are source-backed Python regressions,
not direct execution of native CardPileCmd, full turns or a complete run.

No game launch, profile, save, history or Cloud reads were performed. Scratch
source extractions and logs: `/private/tmp/sts-headless-shuffle-hooks`.

## Implementation

The shared [pile hook module](../../game/headless/core/piles.py) composes owned
plain-data tasks through the existing resolution queue. Bottled Potential now
uses the same native StableShuffle path as refills. Stratagem's choice precedes
Abacus and the triggering draw; its selection does not emit draw hooks. A blocked
full-hand draw does not reshuffle or consume RNG. An explicit empty shuffle still
fires AfterShuffle. Native selector ties retain physical-copy pile order.

Opening Innate cards now match repeated MoveToTop order. Draw-count modifiers
apply before the Innate minimum: six Innate cards plus Bag of Preparation draw
seven cards, rather than eight. Fixture RNG order remains its authored behavior.

Fresh Stomp offers keep their base modifier until entering a combat pile. Entry
subtracts finished attacks while preserving discounts. Ordinary pile moves and
clones do not subtract twice. Existing combat Stomps continue to discount before
attacks; offers do not participate. Unsupported foreign generation and Entropy's
transformation insertion/selection semantics remain outside this change.

Private schemas advance to **combat v16 / run v28**, rejecting earlier schemas.
Restore validates the owned queued shuffle choice and exact native candidate
order. Public observation/action schemas and encoding consumers are unchanged.

## Validation

- Existing focused colorless/potion/draw cases: **291 passed in 18.40s**.
- Final focused shuffle/native combat cases: **283 passed in 1.83s**, including
  **38 new tests** for copy order, RNG suffixes, hook/choice order, JSON restore,
  malformed continuation data, automatic selections, Innate counts/order,
  full/empty piles and generated Stomp modifiers.
- Required independent semantic review: no blockers after correcting automatic
  Stratagem order and Quest rarity. Reviewer independently ran the same 283 cases:
  **1.92s**. No production edits followed this review.
- Affected engine/simulation/headless-backend/package compatibility:
  **385 passed in 6.79s**.
- An additional all-backends run returned **403 passed / 8 failed in 7.63s**.
  The failures are unchanged live-bridge socket/diagnostic fixtures: mock
  `_Socket` lacks `shutdown`, with related diagnostic subprocess failures.
  Bridge tools and their tests have no diff from base `cbf94e1`. These failures
  are recorded separately from the passing affected headless checks.
- Full headless suite: **2,244 passed in 290.86s** (4 minutes 51 seconds).
- One final test-only addition exercises Stomp through actual Attack Potion
  actions and restores both the pending offer and selected free card. All **39
  shuffle-hook tests passed in 0.65s** afterward; production sources were unchanged.
  Its initial artificial RNG seed was correctly rejected by ownership validation;
  the final test uses run seed 13's genuine owned stream.
- `compileall game tests` and `git diff --check` passed.

Built/installed wheel SHA-256:
`3bbfa9d764815612deaca6830d514e0442d9a7a02e1c10a5fbdcd2fe2b881ad7`.
With PYTHONPATH unset outside the checkout, imports resolve from site-packages.
Installed checks pass 24 mixed-pile native vectors, Bottled/Stratagem/Abacus
pending-choice restoration and Stomp entry. Existing installed factory checks
also pass 66 card sequences, 16 boundary cases, 12 potion sequences and four
card/potion continuations. The authored seed-2 slice finishes in 38 commands;
the generated Neow seed-2/right/rest route reaches the boss and loses after 198
commands. Both verify JSON restoration throughout. These are continuation
checks, not native whole-run parity or policy-strength evidence.

Work began at 20:10:05 UTC. Inspection, implementation and independent review
overlapped; separate phase timings were not recorded. Packaging and installed
checks completed around 20:22 UTC; test durations are above. Final documentation
and local integration completed around 20:25 UTC (about 15 minutes total).
No user wait or live release step was needed.

## Next work

The next bounded assignment is dependent native combat interactions: capture
actual multihit targeting/death and spawned-slot sequences, then compare effects,
owned identities, decisions and RNG suffixes against restored Python runs.
Entropy transformation-category/selection RNG, foreign-character Splash and
Kaleidoscope, and the native Act 1 boundary matrix remain in the
[implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
