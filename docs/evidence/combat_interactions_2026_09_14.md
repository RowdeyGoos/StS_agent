# Native attack interactions and automatic death callbacks — 2026-09-14

Scope: pinned 0.107.1 / Steam 23811903, solo Ironclad A0, Overgrowth combat.
Assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

## Executable native evidence

The existing [combat oracle](../../tools/native_combat_oracle/README.md#native-attack-interactions)
now has an `interactions` mode. Its
[32 retained records](../../tests/fixtures/headless_native_interaction_vectors.json)
execute actual AttackCommand.Execute, CreatureCmd damage/death and Infested
callbacks in the assembly's TestMode. Four seeds each cover Slippery, full and
partial block, zero damage, deaths between random hits, and random/fixed/area
attacks through Phrog's Wriggler spawn. Initial HP/block are explicit fixture
inputs. Recorded outputs include per-hit target slots and damage, surviving
creatures, spawned HP, and target/Niche/AI counters and next-double suffixes.

The oracle uses an explicit in-memory A0 context, native creature construction,
constructor-free Player state and synthetic combat-history counters. Local net ID
zero is essential: Hook.AfterDeath otherwise returns without running callbacks.
Player inventory/card hooks are inactive in these attack-command cases; enemy
powers remain active. The proxy returns null for current map-point history and
throws on unexpected accesses. No game launch, player profile, existing save or
history files, or Cloud access occurs. TestMode/presentation-free attack builders
avoid animations; no native rule method is replaced or patched.

The retained mode reproduced every new record. Its original construction/shuffle
and generation modes also reproduced their existing fixtures exactly. Native
execution establishes these bounded attack/death/spawn interactions, not full
card-play wrappers, Horn/Hellraiser execution, full turns or whole-run parity.

## Findings and changes

Pinned AttackCommand `100712501` refreshes living opponents per hit. Fixed-target
commands retain their original target; random/area commands see newly spawned
children. Random singleton selection still consumes a target roll. These paths
already matched Python and now have direct native sequence evidence.

Pinned Slippery `100686143` caps post-block HP loss; `100707670` decrements only
when UnblockedDamage is positive. Older decompiled TotalDamage logic was obsolete.
No Slippery production change was needed; the native block/zero-damage cases now
protect that distinction.

Automatic death callbacks had a concrete ordering mismatch. Hook.AfterDeath
`100711401` visits player relics before enemy powers: Gremlin Horn `100706696`
gains energy and draws before Infested `100707454` spawns. Python spawned first.
With Hellraiser, the drawn Strike could attack a future Wriggler prematurely.
Phrog now queues an owned spawn continuation after the automatic death draw.
No-target autoplay moves its card to its result pile without playing it or
consuming a target roll. Direct lethal damage drains this death work; nonlethal
damage preserves preexisting queued work.

Unfinished Infested work prevents premature victory. Restore validates the exact
owned spawn task, including dead Phrog identity, Infested, no duplicate/missing
work and no foreign slots, before checking its parent/child relationship.
Private schemas advance to **combat v17 / run v29**; old snapshots reject.
Stable enemy slots, public action/observation schemas and encoders are unchanged.

## Explicit remaining limitation

Native death hooks can pause independently. AssignTaskAndWaitForPauseOrCompletion
`100711589` returns when its hook pauses; Hook.AfterDeath ignores the completion
flag and advances. SignalPlayerChoiceBegun `100711593` signals that pause before
waiting for the hook action to resume. Consequently, a Horn draw requesting a
Stratagem choice can let Infested and the enclosing attack proceed first.

The current engine resolves choices serially. Its pending death-work snapshot
tests certify exact serial continuation and ownership, not native detached-choice
timing. The automatic Horn/Hellraiser fix is source-backed Python regression
evidence. Owned pausable hook continuations and native action-queue comparisons
are the next task in the [backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).

## Validation and package

- Initial affected Boomerang/Overgrowth cases: **103 passed in 6.94s**.
- New native interaction and callback tests: **34 passed in 0.25s**.
- Independent semantic review: no blockers after narrowing direct draining to
  lethal transitions; **318 focused cases passed in 2.26s**. Review separately
  checked the native local-ID premise and detached-choice semantics.
- Final focused/affected compatibility suite: **522 passed in 13.88s**.
- Full headless suite: **2,279 passed in 294.20s** (4 minutes 54 seconds).
- Two final test-only direct-damage regressions retain the review's queue-boundary
  checks: all **36 interaction tests passed in 0.26s**; production was unchanged.
- Native oracle build: zero warnings/errors. `compileall game tests` and diff
  checks passed. The first broad run was interrupted for the lethal-only drain
  correction; its incomplete result is not used as final evidence.

Wheel SHA-256:
`bd13956859c1682f88bccb8678929cdcb3da84e513a132ea0f535be3f87d29f8`.
Installed package tests ran outside the checkout with PYTHONPATH unset, explicitly
importing its site-packages: **36 passed in 0.54s**. The wheel's headless Python
sources match the checkout. Installed CLI runs also verified restoration at every
command: the authored seed-2 slice completed in 38 commands with 66 HP; generated
Neow seed-2/right/rest visited 16 rooms and completed nine combats before losing
at the boss after 198 commands. These are continuation checks, not native run
parity or policy-strength evidence.
Scratch logs and source inspections are in `/private/tmp/sts-headless-interactions`.

Work began at 20:28:08 UTC. Native inspection, executable fixture development,
implementation and independent review overlapped; separate phase durations were
not recorded. Final test durations are above. Packaging/installed checks finished
around 20:46 UTC; final documentation and local integration around 20:48 UTC
(about 20 minutes total). The superseded broad run was interrupted after 62.42s
for the review correction. No user wait or live release step was needed.
