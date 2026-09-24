# Neow's Fury choice correction — 2026-09-22

The headless card previously shuffled its discard pile with selection RNG and
returned two/three cards. The pinned native `NeowsFury.OnPlay` attacks first, then
offers an optional discard selection up to two/three cards, capped by available
hand space. The correction uses the existing serializable choice/resolution
machinery. No adapter implements this game rule.

## Reference and scope

[Retained native output](native_neows_fury_2026_09_22.json) binds the pinned game
DLL, engine, runtime dependencies, source-generator and all fixture sources.
The new `--mode neows-fury` extends the existing
[queue runtime](../../tools/native_combat_oracle/queue_runtime/run.py). It executes
the actual native `OnPlay`, attack, selection command and pile movement on
authored TestMode objects. An injected selector records native options/bounds and
returns the specified original card objects. A fresh owned empty user directory
is removed with nonrecursive `rmdir`; no profile/save/history/Cloud data is used.

This probe does not execute the native card-play wrapper, selector UI or complete
combat-ending lifecycle. Exhaust/energy/JSON continuation are separate headless
checks. Existing [live selector evidence](../COMBAT_CHOICES.md) is unchanged and
is not claimed as a live test of the new public contract.

## Compared cases

Each case runs base and upgraded, for 14 native rows:

| Setup | Result |
| --- | --- |
| Four discard cards, select none | Choice opens with minimum zero; no cards move |
| Four discard cards, select maximum in reverse order | Two/three exact originals move in selection order |
| Singleton discard | Choice still opens; base test selects zero, upgraded selects one |
| Empty discard | No selector call |
| Nine cards in hand after attack | Maximum one, exact selected card moves |
| Ten cards in hand, authored in-play/autoplay state | No selector call |
| Attack kills the last enemy | No selector call; combat is ending |

Damage is 10/14 in the unmodified setup. Selection RNG counter stays zero in
every case; headless also matches its next-value suffix. The native test-selector
API receives the raw maximum (two/three even for a singleton); the game selector
UI and headless pending choice clamp maximum to available options. These are
different boundary representations of the same legal selection range.

[Headless comparisons](../../tests/headless/test_neows_fury.py) check pile order,
HP/ending, exact duplicate identities, optional confirmation, toggle/deselect,
selection limits, illegal-action nonmutation and JSON replay after each step.
Adversarial restores reject forged min/max, source, candidate pile, destination
and free-cost data. Old default-catalog saves are intentionally rejected by the
existing content fingerprint because the effect changed. The snapshot formats
remain combat v47/run v68: there is no structural schema change and no migration
or silent reinterpretation of old random-return continuations.

## Affected native harness regressions

The [24-run regression report](native_neows_fury_regressions_2026_09_22.json)
records fresh executions of the 23 previously bound campaign/interaction cases
plus the character-interactions mode. Every result exactly matches its retained
baseline; pins, runtime dependencies and generator identity also matched during
the comparison. Every run exited successfully with empty stderr and verified
owned-directory removal. The report records actual build/runtime durations and
compiled identities. Historical result files and hashes were not repinned.

The first 23 completed in one invocation; the final comparison initially stopped
before execution because the helper used `.json` instead of the retained `.json.gz`
path. Correcting that path ran only the remaining case. No gameplay mutation was
retried and none of the completed 23 was repeated for that correction.

The final Neow probe built in 1.757 seconds and ran in 1.520 seconds. The 24
regression reruns total 40.850 seconds building and 58.748 seconds executing.
The source and cleanup assertions in the tests bind this evidence to the current harness;
a later transitive harness change needs attributable rerun/reuse evidence.
