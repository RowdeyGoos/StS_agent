# Headless engine speedups — 2026-10-17

Status: **complete; behaviour-identical**. The engine got faster without
changing a single game result. This followed a comparison with the Rust engine in
[tfriedel/spire-mentor](https://github.com/tfriedel/spire-mentor), which plays
about 59,000 random fights per second per core against our 149. The goal was the
gains available inside Python; it is not a port.

## Result

Measured on the same machine (Apple M5 Pro, CPython 3.11), against a byte-exact
copy of the pre-change tree (its implementation identity `e63a5121…` matches the
pre-change corpus build):

| Workload | Before | After | Speed-up |
| --- | ---: | ---: | ---: |
| Random-play fights per second, one core | 140 | 218 | 1.55× |
| — the same through the trusted `apply(action, legal=...)` path | 140 | 245 | 1.75× |
| Engine actions per second, one core (trusted path) | 4,240 | 6,120 (7,090) | 1.44× (1.67×) |
| Starter-deck fork | 1.88 ms | 0.96 ms | 1.96× |
| Snapshot capture, real campaign combat state | 1.79 ms | 0.89 ms | 2.0× |
| Adapter state guard (capture + JSON + hash), per call | 2.67 ms | 1.36 ms | 1.96× |
| Snapshot restore, real state | 3.40 ms | 1.32 ms | 2.58× |
| Fork, real state | 5.20 ms | 1.84 ms | 2.82× |
| Greedy network play on 48 benchmark elite/boss openings, one worker | 34.5 decisions/s | 40.3 decisions/s | 1.17× |
| Benchmark corpus collection, 1,024 campaigns, 16 workers | 364.5 s | 301.0 s | 1.21× |

Random play uses the Ironclad starter deck against the 22 Overgrowth encounters
(22.2 actions per fight). Real states are 20 stored benchmark-corpus combat
starts. The network row uses the step-2 initializer checkpoint. The machine was
idle for the A/B; the earlier corpus build's load is unknown. Search time was not
re-measured: forks are about 10% of it, and projection plus inference are 76%.

Agent-layer work dominates realistic workloads. In greedy play the engine's own
code is about 13% of the time. Larger shares go to public-contract validation
(about 28%), feature encoding (22%), trajectory recording (18%) and the adapter
guard (19% before, about 10% after). Those are the next levers. Engine speed
alone cannot reach spire-mentor's scale.

## Changes

- **Legality is computed once.** `RunEngine.apply()` and `CombatEngine.apply()`
  each regenerated the full legal set, on top of the caller's own call.
  - The combat-level re-check is skipped when the run-level inventory sync
    changed nothing.
  - Callers that just enumerated the unchanged state may pass
    `apply(action, legal=...)`. The adapter does so after its existing
    state-guard check, and search worlds after their own projection.
  - Legality had been 46% of random-play time.
- **Repeated derivations removed from hot paths.**
  - Card cost and star cost read `card.spec` once per call, about ten reads before.
  - `Card.spec` indexes levels directly with the same validation.
  - `Deck.find` stops building a list of every card per lookup.
  - The task dispatcher binds its modules once instead of running four imports per task.
  - `status.get` inlines its check.
  - Empty Scythe/Genetic Algorithm loops are skipped.
  - `state_record` replaces `asdict` for intents and potions.
- **Snapshots stop re-deriving constant content.**
  - `RunConfig` computed the shop relic pool once per shop relic, about 1 ms per restore.
  - Restore compares relic, potion, shop and event definitions against cached
    decoded values.
  - Initialization validation reuses a bounded cache of its seed-determined reference.
  - The encounter-tag lookup builds its reverse map once.
  - The card-catalog fingerprint skips re-deriving unchanged immutable
    enchantment definitions.
  - `snapshot(shared_content=True)` embeds the cached content tables for
    read-only use; `fork_combat()` and the adapter guard use it. The default
    snapshot is still detached.

Changed files:
- Engine: `game/headless/{cards,core,encounters,events,generation,powers,run,shops}`.
- Agent: `game/agent/headless/{adapter,full_projection}.py`, plus the `_legal`
  lines in `game/agent/search/{world,observed}.py`.

The snapshot layout and schema versions are unchanged.

## Evidence of identical behaviour

- **Behavioural digest.** `runs/engine-speed-20261017/scripts/equivalence.py`
  runs seeded random play over 300 varied combat starts and 24 full random Act 1
  runs (8,820 steps):
  - The starts vary random Ironclad/colorless decks, upgrades, enchantments,
    relics and potions across all 42 Act 1 encounters.
  - Some fights fork with fresh future seeds partway through.
  - It hashes every legal-action tuple, action, result, error and complete JSON snapshot.
  - The digest `1c1c709e…` is identical before and after every step of the
    work, through both `apply(action)` and the trusted path.
- **End to end.** The rebuilt benchmark corpus reproduces all 1,728 original
  elite and boss openings exactly: encounter, floor, HP, deck, inventory and
  public-state digests. These come from full campaigns played by the network
  collector. The greedy-play A/B played the same 1,022 decisions with 38 wins
  in both trees.
- **Tests.**
  - `compileall` is clean, and all 7,375 headless tests pass, including the new
    `test_engine_fast_paths.py` and content-cache tests.
  - All agent and backend tests pass when run by file. Five test doubles that
    stub `run.apply` now accept and forward its new keyword.
  - `test_runner.py::test_interrupt_after_os_spawn_before_process_handle_attachment_is_reaped`
    fails only when run concurrently with the other agent shards. It passes
    alone and under synthetic CPU load, and the pre-change tree fails it the
    same way in the same parallel configuration.
- **Independent review.** It found no blocking issue.
  - Its probes checked that the trusted tuple equalled a fresh `legal_actions()`
    before all 458 adapter steps.
  - Every combat check skipped across 712 mixed steps was confirmed legal.
  - Its note: the adapter's trusted path relies on its state guard covering
    everything legality reads. It found nothing outside the snapshot.

## Rules bug found, not fixed here

The digest harness found a deterministic rules defect. `attack_multiplier`
returns 1.5 for the Corrupted enchantment, and the damage path keeps the float.
Uppercut enchanted with Corrupted left a Corpse Slug at `hp = 1.0`. The snapshot
encoder then rejects the state ("Unsupported monster state value: float"), so a
search fork in that state falls back. A fix changes game results and needs a
native reference for the rounding. It is a separate change.

Fixed on 2026-11-13. The enchantment now multiplies the card's own damage before
Strength and the other bonuses, in exact integer arithmetic
(`tests/headless/test_corrupted_damage.py`). The digests in this record predate
that fix.

## Reproduce

```bash
sh runs/engine-speed-20261017/scripts/ab.sh <tree> <corpus.json> <label>
PYTHONPATH=. .venv/bin/python runs/engine-speed-20261017/scripts/equivalence.py out.json [--trusted]
```

`ab.sh` expects the pre-change corpus copy in
`runs/engine-speed-20261017/benchmark-pretask` for the old tree. That copy is
4.5 GB of git-ignored regenerable data and can be deleted.

Elapsed times:
- Implementation and profiling: about 2.5 hours.
- Full test runs: about 6 minutes each, sharded.
- Corpus rebuild: 5 minutes.
- Independent review: 11 minutes.
- A/B benchmarks: about 6 minutes.
- User wait: none.
