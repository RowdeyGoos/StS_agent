# Consolidated headless verification — 2026-09-20

Scope: solo Ironclad A0, native build 0.107.1, all unlocked/all seen, on the
headless integration base `de0bd22`. This is a grouped verification and correction
pass, not a declaration of complete game parity.

## Results

- All 16 bounded native fixture modes passed: **955 data rows plus the queue
  lifecycle probe**, zero stderr, unchanged expected results, successful owned
  directory cleanup. Total wall time **55.02 s**, including **25.91 s** building
  and **25.89 s** executing. The [final aggregate](native_verification_final_2026_09_20.json)
  binds current fixture/toolchain/native dependency hashes, each compiled fixture,
  result hashes and exact retained captures. All source hashes matched the final
  working tree at verification time. Historical captures were not repinned.
- Headless suite: **6,336 passed in 511.93 s**. It started before the final Scroll
  Boxes and fixture corrections; the affected checks below cover those final edits.
- Whole repository sweep: **7,630 passed, 11 failed, 63 errors in 632.62 s**.
  This ran before the final corrections. Two failures were subsequently resolved:
  the sandbox-blocked ephemeral localhost test passed in **0.02 s** outside the
  sandbox, and the headless shared-runner identity test now binds its fresh capture.
  The remaining **nine failures and 63 errors** are outside changed headless code.
- Final affected regressions: **345 passed in 115.48 s**, covering ending,
  generated start, corrected reward handoffs, Neow, native RNG, Ancient events and
  three-act progression. The separate matrix identity/results checks passed
  **2 tests in 0.04 s**. These ran after the final relevant corrections.
- Compilation: `python -m compileall -q game tests` passed.
- Independent source review covered ending RNG domains/order, victory versus
  disposal, snapshot semantics, Scroll Boxes RNG consumption and native isolation.

Commands used the existing repository Python 3.11 environment with `PYTHONPATH=.`.
The broad command was `python -m pytest -q`; headless used
`python -m pytest -q tests/headless`. Native reruns used the existing
[`queue_runtime/run.py`](../../tools/native_combat_oracle/queue_runtime/run.py)
with each of its 16 modes, the pinned native runtime, .NET 9/Godot 4.5.1 SDK inputs
and a fresh disposable output directory. See the [runner guide](../../tools/native_combat_oracle/README.md)
for the complete invocation. No live bridge, real profile/history/Cloud access,
installed mod changes or metrics uploads were part of this pass.

## Observed discrepancies and repairs

1. **Architect ending RNG.** Actual native event initialization draws its dialogue
   and creates a fixed-HP creature, consuming one owned event draw and one Niche
   draw. The simulator now consumes both. Twelve [native ending cases](native_campaign_ending_2026_09_20.json)
   cover three seeds with plain/Maw Bank/Wongo/both inventories. Python comparisons
   check counters and RNG suffixes, exact Wongo relic rewards, Maw Bank gold,
   unchanged floor/HP on entry and terminal JSON continuations. Native winning
   serialization retains HP31; later disposal sets HP0. Public headless victory
   deliberately represents the winning state before disposal.
2. **Scroll Boxes draw order.** A [generated seed-0 start](native_generated_start_verified_2026_09_20.json)
   exposed native common/common/uncommon draws per bundle, where headless drew four
   commons before two uncommons. The corrected ordering preserves exclusions across
   both bundles. Native Neow offers, Rewards draw count and the first bundle now
   match. All 15 play/end-turn actions in the generated Nibbit combat match hand
   order, energy, block, enemy HP and player HP. Each Python action is also applied
   to a JSON-restored continuation and compared. No synthetic victories or extra
   HP are used in this native trace.
3. **Native fixture false success.** The older reward-handoff fixture logged a
   missing localization table while starting the Dummy parent event, but its
   process exit and downstream result comparisons passed. Explicit in-memory
   display tables and a three-option assertion repair initialization. The [fresh
   48-case capture](native_reward_handoff_verified_2026_09_20.json) produces the
   same gameplay results with zero stderr. All native runner modes now reject
   stderr; a successful process exit alone is insufficient. Old captures remain
   historical records rather than being silently updated.

Run snapshots move from v53 to **v54** for the changed seeded behavior. Combat
snapshots remain **v35**. Older run snapshots are rejected atomically.

## Whole-suite failures outside this change

Eight `tests/backends/live/` fixture gates fail because legacy socket doubles do
not implement the `shutdown(SHUT_WR)` now used by the bridge probe. They cover room
timeouts, run acceptance/elite/entry, bounded transport, room diagnostics, run-room
wire diagnostics and room-stage diagnostics. Their source and the bridge probe
were unchanged by this pass. Repair the doubles with a checked half-close operation
and rerun those fixture gates under the bridge owner's work.

`tests/differential/test_conformance_evidence.py` and 63 cases in
`test_common_public_subset.py` fail the historical frozen bridge source inventory
binding: expected `a0ca37bb2d0ad36fcb68eafe5163ac8174074b0e6f861c69c2ac357873f75f2a`,
current `6d88f1c4d9f4f510915f5e84672ed7473a3767915fe4453309aafa00a300f1ce`.
These fail before a meaningful current gameplay comparison. Reassess that older
corpus against its actual bridge revision or create separately verified current
corpus evidence; do not repin the old capture just to make the gate pass.

## Exact remaining native acceptance gap

A continuous native campaign through all three acts is **not yet verified**.
The generated-start harness ends after the first combat; the final ending harness
starts from an authored finished boss. Existing Python campaign tests use synthetic
wins to isolate progression and persistence. Combining these records does not
turn them into one native full-game trajectory.

Extend the existing generated-start fixture with legal reward claims, map/room
choices, explicit selection answers and bounded continuation through both act
transitions and the Architect. Retain the seed/path/action trace, inventory and HP,
pending decisions, and RNG counters at each boundary; replay the same choices in
headless with restoration. First establish one complete path, then add the other
Act 1 region. Do not inject victories or increase HP to obtain a parity claim.
Live UI/vote scheduling, arbitrary history/progression profiles, every Dummy outcome
and exhaustive card combinations remain outside this fixture matrix.
