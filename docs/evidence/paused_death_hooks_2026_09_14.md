# Paused death-hook scheduling — 2026-09-14

Scope: pinned 0.107.1 / Steam 23811903, solo Ironclad A0, Overgrowth.
Assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

## Native source findings

Independent inspection of the pinned assembly establishes these rules:

- Hook.AfterDeath `100711401` visits listeners and awaits each
  AssignTaskAndWaitForPauseOrCompletion `100711589`, then continues even when the
  listener has only paused. SignalPlayerChoiceBegun `100711593` signals that
  pause before waiting for its GenericHookGameAction to start.
- ActionQueueSet enqueue/get-ready `100695575/100695577` preserves each player's
  FIFO order. A gathering-choice front action blocks later actions. Repeated
  choices reuse the already active hook action; new nested hook actions append.
- CombatEnded `100695584` cancels waiting/gathering combat actions, preserving
  executing actions. The executor checks combat completion before starting the
  next queued hook (`100711554`).
- FromCombatPile `100712298` performs automatic zero/all checks before signaling
  the choice, then creates its screen from the live pile after that awaited signal.
  Screen update/select `100675343/100675340` refreshes eligible cards. Empty
  completes immediately; a nonempty singleton that was previously deferred still
  needs input. Seeker Strike `100710683/100710682` uses the same live pile command with
  an original sampled-card whitelist; cards that leave the pile are excluded.
  Older decompiled source used FromSimpleGrid and is obsolete for this caller.

During the original implementation batch, native execution was attempted in a
disposable constructor-free fixture using
HookPlayerChoiceContext.MockDependenciesForTest and manual native action driving.
It stopped before reaching the tested behavior: ActionQueueSet's constructor
`100695574` initializes Logger; its static initializer `100694556` calls
GetIsRunningFromGodotEditor `100694551`, whose Godot OS calls precede TestMode.
Without an initialized engine the process exited 139. No game launch, DLL patch,
profile/save/history-file access or weakened safeguard was used. The unvalidated
probe was removed from production; scratch diagnostics remain under
`/private/tmp/sts-headless-paused-review/`.

At that point these queue conclusions were **source-backed, not direct native
execution evidence**. The isolated runtime verification below supersedes that
limitation for the specific queue mechanics it exercises.
The existing 32 actual native attack/death/spawn vectors remain independent evidence
for those commands; they do not execute player card/relic hooks or choice screens.

## Implemented behavior

The existing resolver dispatches explicit death-hook tasks into
`core/hook_scheduler.py`. Automatic Horn energy/draw work stays synchronous. On its
first selection, the hook saves plain continuation tasks and owned card context,
then its parent resumes. Once the parent action finishes, deferred hooks activate
FIFO. Subsequent selections block on that same active hook. No closures, hidden
card piles or global mutable simulator state are introduced.

Stratagem refreshes its candidates only on activation. Later Horn draws can reduce
that choice to one card or empty. Seeker Strike retains its sampled whitelist and
intersects it with the live draw pile on activation; cards drawn or autoplayed by
other hooks disappear. Damage, block, powers and pending card effects identify the currently executing play by context, independently
of the newest physical card in the in-play pile. Waiting work is canceled if the
parent or active hook ends combat, without executing canceled draws or hooks.

Combat **v18** / run **v30** persist the scheduler and reject older private snapshots.
Restoration checks context ownership, task/play joins, one active selector, queued
choice ownership and cancellation boundaries atomically. Stable enemy slots and
public action/observation schemas are unchanged.

## Regression coverage and limits

`tests/headless/test_paused_death_hooks.py` covers parent multihits before visible
Stratagem, live singleton/empty options, canceled final-kill draws, two paused
Seeker plays, replay choices, root card choices blocking queued hooks, RNG stability,
JSON restoration and malformed cross-context state. Interaction tests now expect
Infested and the parent play to have finished before exposing the Horn choice.

Native enemy-side execution is not a single queued player action. Pinned
SetReadyToBeginEnemyTurn `100697597` starts its coroutine asynchronously;
ExecuteEnemyTurn `100712561` awaits individual turns and pause checks;
EndEnemyTurn `100712553` reaches the next player turn without an action-queue-empty
wait. Exact enemy-side/queued-hook interleaving therefore requires runtime evidence.
This batch does not claim complete enemy-turn, multiplayer or whole-run parity.

## Validation

- Focused card/relic/potion checks before the final Seeker correction: **601 passed
  in 45.58s**.
- Final affected paused-hook/interaction/shuffle/colorless tests: **240 passed in
  9.87s**. Independent semantic review reran the same scope: **240 passed in
  9.88s**, with no remaining blockers in the declared scope.
- Final simulation, encoder, CLI and engine compatibility: **238 passed in 1.77s**.
- Final full headless suite: **2,296 passed in 296.75s** (4 minutes 56 seconds).
- `compileall game tests`, diff checks and wheel source comparison passed. All
  **157 headless Python files** in the wheel match the checkout.
- Installed package outside the checkout, with PYTHONPATH unset and explicitly
  verified site-packages imports: **51 passed in 1.60s**.
- Installed CLI restore-at-every-command checks: authored seed 2 completed the
  slice in **38 commands / 66 HP**; generated Neow seed 2/right/rest visited
  **16 rooms / nine completed combats / 198 commands**, ending in boss defeat.
  These are continuation checks, not native run parity or policy-strength results.

Wheel SHA-256:
`9375f9946a8719ac1bf7933798a81767a0bb814fbeab489fbf95d910506523f4`.
Scratch wheel: `/private/tmp/sts-headless-paused-hooks/wheel/`.

An earlier full run passed **2,296 tests in 298.46s**, then the Seeker live-pile
correction changed production. That earlier result is superseded by the final
run above. Package and installed checks completed around 21:17 UTC.

Work began at 20:53:49 UTC; implementation, source inspection and independent review
overlapped, so separate phase timings were not measured. No user wait or live
release was required. Final validation and local integration finished around 21:22 UTC
(about 28 minutes elapsed).


## Direct native queue verification follow-up

The optional [isolated runtime fixture](../../tools/native_combat_oracle/queue_runtime/run.py)
now executes actual pinned HookPlayerChoiceContext, GenericHookGameAction and
ActionQueueSet methods. The [retained native record](native_hook_queue_2026_09_14.json)
binds engine, assembly, GodotSharp, all supplied runtime dependencies, fixture
source and compiled output hashes. Final execution used MegaDot
`v4.5.1.m.12.mono.custom_build`; stderr was empty and the process exited zero.

Synthetic tasks A and B request choices before either becomes visible. The outer
fixture then continues; native queue driving exposes A's first choice, resumes A
into its second choice using the same action, finishes A and finally exposes B.
Both A choices block B. Separate native CombatEnded calls cancel two waiting
hooks, then a gathering hook plus a waiting hook. The queue becomes empty and
canceled coroutine tasks remain suspended until the isolated process exits.

The fixture uses an explicit constructor-free player, synchronizer dependencies,
executor ownership field and a singleplayer-only network proxy. It manually calls
actual GameAction.Execute; it does not execute the ActionExecutor frame loop,
Horn, shuffle/draw commands, card-selection screens, enemy turns or a native run.
Those compositions remain open. Existing Python tests cover their modeled
behavior and restoration, not direct native selector parity.

The custom project has no game autoloads, extension manifest or native game pack.
Exported hosting requires `_custom_features="dotnet"`. The native assembly loads
in the fixture's component assembly context and verifies that it resolves the
same initialized GodotSharp assembly. Loading it into Default had instead caused
an uninitialized interop call in Logger during fixture development. No native
methods or binaries were patched. A fresh owned empty Application Support
directory supplies Godot's user directory and is removed with nonrecursive rmdir;
no real profile, save, history or Cloud directory is accessed.

Final validation:

- Native fixture build: **1.220s**; execution and owned-directory cleanup:
  **1.305s**, all assertions passed.
- Existing paused-hook regressions: **15 passed in 0.85s**.
- Independent semantic/isolation review: no blockers; six file/symlink output
  collision cases rejected before staging and preserved their inputs.
- Both the final runtime and earlier bootstrap Godot user directories were
  removed. Runtime logs and build outputs remain in the disposable output folder
  `/private/tmp/sts-native-queue-final/`.

No production engine or schema changed, so the prior full gameplay/package
validation remains applicable; this follow-up adds native verification tooling
and evidence only. Work began at 21:32:23 UTC; the final runtime check completed
at 21:54 UTC (about 22 minutes). Most elapsed time was spent bootstrapping isolated
exported .NET hosting; implementation and review overlapped. No user wait or game
installation was required.
