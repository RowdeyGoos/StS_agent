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

Native execution was attempted in a disposable constructor-free fixture using
HookPlayerChoiceContext.MockDependenciesForTest and manual native action driving.
It stopped before reaching the tested behavior: ActionQueueSet's constructor
`100695574` initializes Logger; its static initializer `100694556` calls
GetIsRunningFromGodotEditor `100694551`, whose Godot OS calls precede TestMode.
Without an initialized engine the process exited 139. No game launch, DLL patch,
profile/save/history-file access or weakened safeguard was used. The unvalidated
probe was removed from production; scratch diagnostics remain under
`/private/tmp/sts-headless-paused-review/`.

These queue conclusions are **source-backed, not direct native execution evidence**.
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
