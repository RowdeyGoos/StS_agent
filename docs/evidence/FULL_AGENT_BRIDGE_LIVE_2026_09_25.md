# Full-agent bridge live coverage, 2026-09-25

This controlled Profile 3 batch exercised the shared `agent_v2` interface on
the pinned macOS game 0.107.1 / Steam build 23811903. The user launched manually;
native Continue resumed the existing assisted Ironclad test run. This is bounded
interaction evidence, not an uninterrupted campaign or a policy-strength result.

## Tested artifact

- Source: `6c043278311dac931903e4dc110f43e8264bac2f`; feature `cc9fa81`.
- Manifest SHA-256: `32d721e8f6f680d6fc0eeccfe90eeb5926dcbe17ac605cab43b89b36561ec314`.
- DLL SHA-256: `470e6b75f5d57ceefa706c86ca62e5ad264de203f8b3300a3f183c6ffcac3fc8`.
- Release evidence: `/private/tmp/sts-bridge-d2n3wh6m`.
- Installed state SHA-256: `bb10686579d284b506e80cfd7191e1f7545eb8c0211aa1d8b97d78343161cd6f`.

Health, pinned-build compatibility and current process checks passed. An initial
client invocation used a relative manifest path and failed local preflight before
any gameplay action; the absolute-path invocation passed. All gameplay actions
below used the existing authenticated client, shared adapter and advertised
public candidates. Short test policies selected the intended alternatives.

Native console setup was performed only between settled cases: add Driftwood,
Fruit Juice, Gambler's Brew and two separate Skill Potions; later remove Driftwood
and add Pael's Wing. The existing assisted deck and HP were otherwise retained.
Only ordinary UI Save and Quit was used; no profile/save/history/Cloud content
was inspected, and public trajectory recording stayed disabled.

## Outcomes

Counts are cumulative attempted / accepted / reconciled within this bridge
process. Reads belong to the named controller segment; treasure and second-combat
reads exclude their separate initial map-entry observation.

| Case | Result | Counts | Reads |
| --- | --- | --- | --- |
| Rest → Dream Catcher reward → Reroll → choose card → Leave | Passed; actionable map, HP 45/83 → 69/83, deck 6 → 7, gold 399 unchanged | 5 / 5 / 5 | 30 |
| General potion discard at map | Passed; Regen Potion's exact slot became empty | 6 / 6 / 6 | 2 |
| Fruit Juice at map | Passed; HP 69/83 → 74/88, potion consumed | 7 / 7 / 7 | 2 |
| Connected treasure → Open → Claim → Leave | Passed; relic obtained, actionable map, gold 399 → 449 | 11 / 11 / 11 | 54 |
| Connected combat → Gambler's Brew → select one hand card → confirm | Passed; discard/redraw completed and combat became actionable | 15 / 15 / 15 | 53 |
| Skill Potion → select an offered card | Passed; Expect a Fight appeared in hand | 17 / 17 / 17 | 18 |
| Second Skill Potion → zero-selection confirmation | Passed; optional offer skipped, combat actionable | 19 / 19 / 19 | 16 |
| Finish combat → gold/potion → first Sacrifice → Leave | Passed; Pael's Wing counter 1, actionable map | 28 / 28 / 28 | 27 |
| Next connected combat → rewards → second Sacrifice | Failed `read_native_failed`; Whetstone visibly granted, card menu closed, one action remained pending | 36 / 36 / 35 | 107 |

Successful segments ended with no pending action. The final failed action was
not retried or adopted as reconciled. The UI showed HP 86/88, gold 485, deck 7,
Pael's Wing's displayed counter 0 and Whetstone; a Flex Potion reward remained.
The displayed counter is modulo two and is not evidence of an incorrect reset.

## Correction and its evidence boundary

The automatic-effect observer hooked the small single-card `CardCmd.Upgrade`
forwarder. Native Whetstone calls it, while the underlying mutation occurs in
`CardModel.UpgradeInternal`. Runtime inlining can bypass the former hook. The
old fixture suppressed inlining and omitted Whetstone's pickup behavior.

A native-shaped enumerable-command/model-upgrade regression failed against the
old observer with `reward_alternative_boundary`
(`/private/tmp/sts-bridge-9xof8ceh`). The correction observes the actual model
mutation, retaining exact ownership, scope, eligibility, +1 level and unchanged
survivor checks without enumerating a random target sequence. Cases cover zero,
one and two eligible originals, unscoped upgrades and sticky cleanup failure.
Alternatives, shop effects and shared event reward tests passed in 7.598 seconds
(`/private/tmp/sts-bridge-r_ry81oh`). Independent semantic review found no blocker
(14:13:45–14:14:26 UTC, 41 seconds), following an 86-second source investigation.
The original live failing predicate was not captured at this finer boundary;
inlining remains the source-supported explanation pending a live retest.

## Cleanup and timing

Normal Save and Quit and game Quit were followed by verified stopped process and
closed listener. The exact owned files were quarantined and purged: four generated
files removed, zero overlays, all 429 base files unchanged. Base SHA-256 remained
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`bf83d500d73bd79d5691340cdeeb956b1cbf97ffa48802bdf25d69d5466baa2d`.

Work resumed at 13:50:24 UTC; cleanup was verified by 14:09:44 UTC. This interval
includes setup, tests and initial diagnosis; exclusive execution and user-wait
times were not measured. Clean installation removal does not change the failed
gameplay reconciliation. Subsequent packages must retain this result under its
original artifact identity.
