# Conditional relic stat changes — 2026-09-20

Red Skull and Belt Buckle now route positive and negative stat changes through
the existing power rules. Removing their bonus is a debuff, so Artifact can
prevent the loss. The relic still becomes inactive when its condition stops
holding. A later activation grants a new bonus; it does not subtract or reuse
the protected amount. Ruined Helmet doubles only the first positive Strength
application, and both directions are suppressed once combat starts ending.
Relic activation flags still track the condition when power application is
suppressed, including Red Skull's lethal HP change.

The previous implementation directly subtracted Red Skull Strength and wrote
Belt Buckle Dexterity, bypassing Artifact. Red Skull also bypassed the ending
guard on both gains and losses. There is no new state field or snapshot format:
the saved flags retain their existing meaning as condition/activation state,
not the amount of the bonus remaining after power modifiers.

## Native comparisons

The [fresh capture](native_conditional_relic_stats_2026_09_20.json.gz) contains
**72 new cases at 720 boundaries**, plus an unchanged rerun of all 144 previous
item/status cases. New cases vary seeds 0/2/42, A0/A10, Artifact absent/present,
and these six scenarios:

- Red Skull, Red Skull with Ruined Helmet, or Belt Buckle.
- Each begins in active combat or at an authored combat-ending boundary.

Each scenario repeats activations and deactivations, including duplicate
callbacks. Normal-combat variants also test losing/reapplying the bonus after
combat begins ending. Comparisons include every active player power ID/amount,
HP/max HP, potion count, the active flag, Ruined Helmet's used flag and the ending
condition. All **648 transitions** replay from JSON on the Python side.

Examples with Artifact 1:

| Relic | First activation | First deactivation | Second activation |
| --- | ---: | ---: | ---: |
| Red Skull | Strength 3 | Strength 3; Artifact consumed | Strength 6 |
| Red Skull + Ruined Helmet | Strength 6 | Strength 6; Artifact consumed | Strength 9 |
| Belt Buckle | Dexterity 2 | Dexterity 2; Artifact consumed | Dexterity 4 |

Without Artifact, deactivation removes the base bonus (3 Strength or 2 Dexterity),
even when Ruined Helmet amplified the initial application. Duplicate callbacks
do not apply the change twice. Ending variants preserve Artifact and do not mark
Ruined Helmet used, since no power amount is applied.

The existing isolated `queue_runtime --mode item-status` invokes actual relic
callbacks and native `PowerCmd` on authored combat objects. HP/potion membership
changes and the enemy's ending HP are supplied by the fixture; this does not
claim native HP/inventory command dispatch, a complete combat-end lifecycle,
live UI or native disk saves. These conditional rules make no random choices;
the seed/difficulty variants check invariance rather than RNG distribution.
Separate Python tests exercise HP-loss/healing dispatch, generated potion
procurement and discard through run synchronization. Negative initial stats and
lethal player HP changes are additional source-backed Python regressions.

## Provenance and validation

The native assembly remains pinned to 0.107.1, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Native build took **1.885 seconds** and execution **2.008 seconds**, with empty
stderr and removal of the unique owned user directory. No game profile, save,
history or Cloud data was accessed.

Only `queue_runtime/item_status.cs` changed in the native harness. The new
capture binds the current sources and proves the previous 144 parsed results
are identical. The campaign/event/reward implementations and dispatcher remain
byte-identical to the earlier 13-run report; assertions retain that dependency
comparison. Historical captures and their source identities were not repinned.

Final focused validation passed **618 tests in 16.89 seconds**:

```bash
PYTHONPATH=. python -m pytest tests/headless/test_conditional_relic_stats.py \
  tests/headless/test_relic_combat.py tests/headless/test_potions_complete.py \
  tests/headless/test_native_item_status.py \
  tests/headless/test_native_event_branches.py::test_current_harness_and_unchanged_native_campaigns_are_bound \
  tests/backends/headless -q --durations=5
```

Compilation, diff checks and independent semantic review passed. The full
headless suite was not repeated for this two-hook correction. Implementation
and review elapsed times were not separately measured.
