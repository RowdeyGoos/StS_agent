# PPO training throughput — 2026-10-18

Status: **complete; bit-identical**. Production-shaped combat PPO now runs
**1.36× faster**. It plays the same episodes, reports the same update metrics and
ends with byte-identical weights. Collection is 1.94× faster. The update phase is
unchanged and is now 60% of wall time. This follows the
[engine speedups](ENGINE_SPEED_2026_10_17.md), whose report named agent-layer
costs as the next lever.

## Result

The benchmark used the production training shape on one machine (Apple M5 Pro
with 6 + 12 cores, CPython 3.11, PyTorch 2.13):
- the step-2 frozen configuration and initializer;
- 16,384 decisions per invocation, in four 4,096-decision rounds;
- 16 spawned collectors and four strict deterministic update threads.

Three pre-task/final pairs ran interleaved:

| Per invocation | Pre-task tree | Final tree | Speed-up |
| --- | ---: | ---: | ---: |
| Total | 78.6–79.2 s | 57.7–57.9 s | 1.36× |
| Decisions per second | 207.0–208.5 | 282.8–283.9 | 1.36× |
| Collection | 43.3–43.6 s | 22.3–22.6 s | 1.94× |
| — worker startup | 9.5 s | 0.1 s | |
| — slowest worker, per round | 7.7–8.2 s | 5.1–5.3 s | 1.5× |
| — result transfer after the last worker, rounds 2–4 | 0.47–0.72 s | 0.15–0.27 s | |
| Updates | 34.4–34.7 s | 34.4–34.6 s | 1.00× |

In the final tree the first round still has about 1 s of overhead, because
collectors finish importing after start.

The pre-task tree already includes the engine speedups. For context, the step-2
production run measured 90.9 s per invocation (180 decisions/s) before either
change.

Single runs of the intermediate steps, on the same workload, show what each
change contributed:

| Step | Total | Decisions/s |
| --- | ---: | ---: |
| Pre-task reference | 77.0 s | 212.9 |
| Asynchronous collector startup | 69.5 s | 235.6 |
| Guard text reuse, contract fast paths, reference memo | 65.3 s | 250.9 |
| Flat-row table packing | 60.9 s | 268.8 |
| 1 MiB pipe buffers | 57.9 s | 283.1 |

Per-call costs in one process, on stored corpus combat starts:

| Collector step per decision | Before | After |
| --- | ---: | ---: |
| Adapter observe (guard, projection, preparation) | 4.53 ms | 3.01 ms |
| — state guard | 1.34 ms | 0.88 ms |
| — prepared-record validation clone | 1.47 ms | 0.53 ms |
| Recording wire conversion | 0.75 ms | 0.32 ms |
| Lossless table packing | 2.38 ms | 0.99 ms |

Packing saved more under 16-way load than in one process. Worker rounds fell by
about 1.5 s after that change alone, consistent with the old version's roughly
5,000 small list allocations per decision.

## Changes

All changes are in the agent layer; `game/headless/` is unchanged.

- **Collector startup** (`training/parallel.py`).
  - Spawn used to pickle the startup state into every child's arguments,
    including the environment factory with its loaded corpus (2.4 MB). The
    parent waited about 0.5 s per collector.
  - The state is now pickled once and sent as the first pipe message by each
    transfer thread. The collector polls for it and honours a stop request
    before it arrives.
  - Because one byte string serves every collector outside spawn's inheritance
    context, the state must be plain picklable data. Multiprocessing locks,
    queues and connections are no longer accepted; no existing environment
    factory carries them.
- **Pipe buffers** (`training/parallel.py`).
  - Duplex pipes are socket pairs, with 8 KiB buffers by default on macOS.
    Receiving 16 rollouts of about 54 MB each took 0.73 s per round. With
    1 MiB send and receive buffers it takes 0.14 s.
  - Bytes and message order are unchanged. Buffers are only ever raised.
    Platforms that refuse the option keep their defaults.
  - The pipes stay blocking even if a process-wide default socket timeout is
    set, as `Pipe()` itself ensures.
- **State guard** (`headless/adapter.py`).
  - The digest string is still byte-identical to the sorted compact JSON of
    the full snapshot. It is built per top-level key.
  - The JSON text of the shared, immutable item, shop and event definitions is
    computed once per content object.
- **Public contracts** (`contracts/codec.py`, `contracts/full.py`).
  - Exact `Node`, `Field` and `Link` records use specialized wire converters,
    with the same key order, element order and error positions.
  - `PreparedPublic` clones exact-typed decisions directly. Any other type, and
    any input deeper than the contract limit, still uses the generic schema
    reader. `validate()` runs in both cases.
- **Table packing** (`encoding/full_records.py`).
  - Rows are stored flat and converted to one int64 array.
  - Text interning is inlined, and the reference-pattern match is memoized per
    string.
  - Every row is still reserved and capacity-checked before its value is
    interned, so the first capacity error is unchanged.

## Evidence of identical behaviour

- **Training.** Every candidate run was compared with the pre-task run, for all
  three interleaved pairs and every intermediate step. All of the following
  matched:
  - every stable field of all 1,185 episode records (outcome, steps, return,
    HP, case and action counts);
  - all update metrics;
  - the final weights;
  - the saved Adam moments, both learner RNG states and the counters.

  Only random episode IDs, file names derived from them and wall times are
  excluded.
  - Corpus case IDs are random, and the sampler orders cases by ID. Each tree
    therefore used a corpus built for its own source identity that replays the
    baseline's ID allocation. Every build reproduced all 2,167 cases.
  - A first interleaved attempt was discarded. Its baseline config had been
    overwritten with a 512-decision rollout by an earlier profiling setup.
- **Packing.** The check covered 1,486 decisions from 60 corpus starts, across
  combat, reward, map, event, rest, treasure, shop and act-transition screens.
  - Tables, mapping results and dtypes were identical.
  - 32,032 reduced-capacity and integer-magnitude cases raised identical errors.
- **New tests.** `tests/agent/test_collector_fast_paths.py` plays seeded random
  campaigns. Against independent references, it compares:
  - the guard digest with the full JSON dump;
  - the clone and wire output with the generic reader and writer;
  - error messages for malformed records;
  - specialized tables with generic packing.

  Each test fails when a deliberate defect is injected into its fast path.
  `test_ppo_parallel.py` gains a pipe-buffer test. Its blocked-send test now
  asserts a payload larger than four times the new buffer.
- **Test suites.**
  - `compileall` is clean.
  - All agent, backend and layout tests pass: 1,876 passed and 1 skipped
    across 86 files, run in eight shards.
  - `test_runner.py::test_interrupt_after_os_spawn_before_process_handle_attachment_is_reaped`
    again failed only under parallel shards and passes alone, as recorded on
    October 17.
  - The headless suite was not rerun, because no engine file changed.
- **Independent review.** It found no blocking issue in production code.
  - Its probes covered:
    - 26,768 `PreparedPublic` variants and 26,588 wire cases, with no
      difference in value, key order or error;
    - 6,916 packing cases;
    - guard digests on 603 real decisions;
    - startup fault injection: a dead worker before or after startup, slow
      readers with cancel or deadline, and an unpicklable factory. There were
      no leaked processes or threads and no hang.
  - It raised four points, all fixed:
    1. The new pipe test assumed 1 MiB buffers on Linux, which caps them. It
       now asserts growth, and 1 MiB on macOS only.
    2. Wrapping the pipe fd would apply a process default socket timeout and
       leave the pipe non-blocking. The helper now restores blocking mode, and
       a new test covers it.
    3. The startup state is accepted in fewer cases, as documented above.
    4. A hand-built record with unset slots could raise a different first
       error. The wire converters now read fields in the generic order, and
       the clone defers to the generic reader on `AttributeError`.
  - After the fixes:
    - 1,877 tests pass.
    - A matched production run took 57.5 s (284.9 decisions/s) and remained
      fully bit-identical to the pre-task run.

## Measured and not adopted

- **Update phase.** Each round runs 512 optimizer steps at 11.7 ms each, plus
  two full-rollout KL passes of 1.34 s each. A step splits into:

  | Part | Per step |
  | --- | ---: |
  | Forward | 5.0 ms |
  | Backward | 4.8 ms |
  | Adam | 0.7 ms |
  | Collation | 0.5 ms |
  | Parameter check | 0.3 ms |

  Exact alternatives gave nothing worth taking:
  - Foreach Adam is bit-identical but slower (8.56 vs 8.37 s per update).
  - `index_select` embeddings have bitwise-equal gradients and no speed gain.
  - A fused parameter-finiteness check saves 0.07 ms per step, about 0.2%.
- **Update threads.** Four threads is fastest: 2, 4, 6 and 8 threads take 9.70,
  8.37, 9.17 and 10.17 s per update round. Each thread count gives a different,
  deterministic result.
- **Episode reset.** A reset costs about 15 ms, including the frozen-state
  public digest. The digest uses Python's indented JSON writer and takes 3.4 ms.
  Resets are about 2% of run time.

## Remaining options that change semantics

None of these are implemented; each needs a decision and, for learning, a
paired comparison.

1. **Overlap the final KL pass with the next collection.** Weights stay
   identical, but report and checkpoint timing change. It could save up to
   about 5 s per invocation.
2. **Asynchronous PPO.** Collecting the next round with the previous policy
   approaches max(collection, update), up to about 1.6×. It adds a one-round
   policy lag.
3. **Fewer or cheaper KL passes.** One example is the existing minibatch check
   in place of the epoch-1 full pass. That would save up to 2.7 s per round but
   changes early stopping.

## Reproduce

Scripts and result summaries are in `runs/training-speed-20261018/{scripts,results}`.
They are git-ignored local data. The corpora and runs there, about 2.7 GB, can be
regenerated.

```bash
sh runs/training-speed-20261018/scripts/ab_train.sh <pre-task tree> <final tree> 3
PYTHONPATH=. .venv/bin/python runs/training-speed-20261018/scripts/compare_train.py <left run> <right run>
PYTHONPATH=. .venv/bin/python runs/training-speed-20261018/scripts/pack_equivalence.py <pre-task tree>
```

Elapsed time, from the pre-task tree copy at 00:20 to the final A/B, was about
1 h 50 min including measurements:
- Each matched corpus build: about 140 s.
- Each sharded test run: 160 s.
- Each three-pair A/B: about 7.5 min.
- Independent review: 21 minutes.
- Fixes and confirmation after review: about 10 minutes.
- User wait: none.
