# Headless test overhead improvements — 2026-09-20

Baseline: `codex/headless-integration` at `4d541e9`, using the existing Python
3.11 virtual environment on the same machine. The preceding headless run passed
7,078 tests in 1,675.74 seconds (27m55s). Collection took only 1.78 seconds;
repeated replay and snapshot work dominated execution.

## Changes

- Native event replay now keeps its prefix key separate from the RNG comparison
  loop variable. Previously every cached snapshot was stored under `"shops"`,
  so no parent lookup could hit. The matrix releases prefixes when the seed,
  ascension, enhancement or selection configuration changes, avoiding retention
  of thousands of unrelated full snapshots.
- The campaign helper reuses snapshot values already taken at the same boundary:
  five captures per command instead of eight. Both restores, both action
  applications, legal-action comparisons and snapshot equality checks remain.
- Crystal Sphere restore checks board geometry, retained placement attempts,
  reward subscriptions, revealed items, legal options and the chosen page history
  directly. It no longer executes every offered click merely to validate a page.
  The original profile executed `cleared()` 41,617 times for 78 actual commands.
  Chosen transitions and reward/curse receipts are still evaluated and checked.
- Relic/potion, event and shop catalogs retain one JSON representation only for
  recursively immutable definitions. Every read returns detached containers;
  membership, ordering and definition replacements invalidate the cache. Mutable
  custom definitions bypass it. Cached content contains no run state.

Valid serialized snapshots retain their previous values and formats. New Crystal
Sphere validation rejects malformed board/history combinations more directly;
no compatibility version bump or native evidence repinning was needed.

## Matched sample timings

Three unprofiled repetitions per workload, medians in seconds. Each repetition
keeps the original native boundary and RNG assertions. Aggregate SHA-256 of final
serialized snapshots matches the baseline for every sample. Cold and warm static
catalog JSON also matched the pre-change serialization byte for byte.

| Workload | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| First 64 Fake Merchant rows | 3.292 | 1.678 | 1.96× |
| First 12 Crystal Sphere rows | 3.760 | 0.962 | 3.91× |
| First 40 campaign commands | 1.764 | 1.010 | 1.75× |

The campaign sample is a diagnostic prefix, not a new complete-run victory claim.
These contiguous samples do not represent every seed or act. Raw repetitions,
snapshot digests and relevant source hashes are in the
[timing record](headless_test_overhead_2026_09_20.json).

The final broad gate passed all 3,852 Fake Merchant rows in 117.47 seconds
(previously 294.28) and all 780 Crystal Sphere rows in 74.46 seconds (previously
279.15). Its eight listed campaign replays took 285.40 seconds combined, compared
with 469.69 seconds previously. This run includes scenario-scoped cache retention.

## Validation

Focused event/catalog regressions passed 112 tests in 10.18 seconds. Independent
semantic review found no blocking issues and ran the 26 new cache, Crystal Sphere
and prefix-reuse regressions in 0.89 seconds. Adversarial restores recompute the
continuation checksum to reach semantic validation, then verify atomic rejection.
A forced ten-attempt placement checks retained items and repeated subscriptions.

The final broad gate passed **7,261 tests in 878.78 seconds (14m38s)**, including
all headless tests and the headless backend consumers. This is **47.6% less wall
time** than the preceding 7,078-test headless run (27m55s), despite including 26
new regressions, the previous change's final potion-discard test and 156 backend
tests. This wider-suite comparison is observational; the matched samples above
provide the controlled workload comparison. No tests were skipped or workers added.

`compileall game tests`, diff checks and independent semantic review passed.
No native game process was launched; retained native captures and their original
assertions are the integration evidence for these Python-only changes. Native
capture files and source bindings are unchanged. Timings above cover validation
only; separate implementation/review wall times were not recorded.

## Reproduce

```bash
PYTHONPATH=. python -m pytest tests/headless/test_content_snapshot_cache.py \
  tests/headless/test_crystal_validation.py \
  tests/headless/test_native_event_branches.py -q --durations=10
PYTHONPATH=. python -m pytest tests/headless tests/backends/headless -q --durations=15
python -m compileall -q game tests
```

For sample measurements, replay the first 64/12 rows from the retained Fake
Merchant/Crystal Sphere captures with `native_event_replay.replay(row, cache)`.
The campaign sample uses `native_route_replay.replay_route(..., boosted=True)`
and stops before command 41 through a wrapper around its `step` helper. Compare
serialized snapshot digests as well as timings. Do not run profiling or other
tests concurrently with timing samples. Full native matrices remain in the broad
gate; use affected modules during development rather than repeating that gate.
