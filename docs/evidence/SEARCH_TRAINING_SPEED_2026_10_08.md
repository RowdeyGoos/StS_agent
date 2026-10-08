# Search training speed — 2026-10-08

This follow-up benchmarks four optimizations against the implementation used for
the corrected Vantom comparison, after the earlier compact-inference work and
coverage repairs. It preserves the search budget and the public-information
boundary. No new 50,000-decision training round or held-out evaluation is run.

## Changes

1. **Prepare training data once.** Reuse the loaded, validated trajectory when
   checking its training sidecar. Build feature arrays only for supported searched
   decisions. Omitted decisions still receive public capacity, catalog and action
   checks and remain part of episode returns and corpus identity. Truncated
   episodes retain missing value labels.
2. **Reuse prepared public observations.** Apply simulated public context and
   history transformations before creating the immutable owner. Pass that exact
   owner into inference, retaining capacity checks. Custom encoders, structural
   records and their reference ordering keep their ordinary path.
3. **Cache immutable card descriptions.** A process-local LRU holds at most 2,048
   descriptions keyed by every validated public field and its exact type. Dynamic
   costs, modifiers, piles, identities and legal actions are rebuilt normally.
4. **Cache repeated predictions.** Within one real search decision, keep at most
   128 predictions for exact typed public inputs, including history, references
   and candidate order. Only the frozen built-in provider opts in. Custom hooks
   and trainable providers keep their ordinary path. Clear the cache on completion
   or exception. Every simulation still samples and advances its own world;
   rollout returns and mutable tree statistics are never cached here.

These changes are automatic. Search remains an experimental opt-in controller.
Card-description reuse also benefits ordinary headless observations; the new
prediction cache and prepared-world handoff are specific to Search. The loader
improvement applies to search distillation. PPO's learning algorithm is unchanged.

## Controlled setup

The baseline is build
`357142e7dd5d321cfa707fc6b444c1306fa8e01503542f8af887317a23950039`.
The final build is
`322f129e4bd1a4124603dcb760302da9fdcf362a110a877835ce913585c97a22`.
Both use unchanged headless rules
`efcc2494d3c1f896669e334cb49a60455048ac4f2a44a3466a7a62225cd0771c`.

Use 16 training source groups, eight openings and eight continuations, from the
existing Vantom corpus. Their public prefixes and private evaluator starts reuse
the corrected rules proof and must pass exact hash/public-start checks. The
planner receives only the public anchor and observations. Follow existing split
delegations before replay; no held-out start is deserialized or played.

Use the original specialist initializer, 24 simulations, four leaf actions,
depth 16, two belief particles, exploration enabled, and 16 spawned workers with
one Torch thread each. Search and belief ceilings are 120 seconds. Every trial
rejects unsupported fallbacks, incomplete simulation budgets, timed bootstraps or
search cutoffs. Forced actions remain separate. Each implementation runs from
its own immutable package snapshot with canonical imports and a checked source
identity. Timing trials run sequentially, without concurrent test/profile jobs.

All reported whole-batch times include worker startup, model loading, admission
checks, recording and shutdown. Three repetitions use changing variant order.
The cache ablation includes prepared-input reuse, so its incremental effect is
measured against that arm. A later compatibility-only adjustment avoids importing
optional inference dependencies for custom public policies; a separate final
protocol binds it without changing earlier ablation evidence.

## Individual ablations

The short collection panel executes eight real actions per start. Each trial has
**128 decisions, 108 searched decisions, 2,592 simulations and 10,332 leaf steps**.
The other 20 decisions are forced. All 15 trials have identical full public
trajectories, chosen actions, search distributions, values, visits, tree/leaf
work, returns, remaining HP and potion use.

| Change | Reference median | Optimized median | Less wall time |
|---|---:|---:|---:|
| Prepared-observation reuse | 21.72 s | 20.17 s | 7.1% |
| Immutable card descriptions | 21.72 s | 20.94 s | 3.6% |
| Prediction cache, added to prepared reuse | 20.17 s | 19.85 s | 1.6% |
| All search changes together | 21.72 s | 18.94 s | 12.8% |

The combined trials span 18.83–19.48 seconds; the baseline spans 21.63–21.85.
Prediction-cache hits are 903 of 12,996 requests per trial (6.95%). This is a
modest incremental benefit; it does not remove most inference. Maximum observed
worker resident-memory high-water marks rise from about 329 to 349 MiB. These
are individual process maxima, not simultaneous system-memory measurements.

Prepared reuse moves final-observation validation from the inference timer into
projection. Compare complete time or their combined cost; a larger projection
timer alone does not demonstrate a projection regression.

## Training-data preparation

Load a byte-identical subset of the finished collection: 26 episodes and 625
real decisions, producing 487 search examples. Four examples retain missing
value labels. Compare three runs each of the baseline, loader-only optimization,
and combined implementation, using four Torch threads for the learner probe.

| Loader | Median | Observed range |
|---|---:|---:|
| Baseline | 10.28 s | 9.96–10.87 s |
| One-pass preparation | 7.06 s | 7.01–7.13 s |
| Combined implementation | 7.32 s | 7.13–7.32 s |

The isolated loader saves 31.4%; the combined implementation saves 28.8%.
Every run reproduces the exact corpus identity, feature arrays/dtypes, action
mapping, normalized distributions and value labels. Three identically seeded
learner updates also reproduce every reported loss/update metric and final
parameter bytes. These are discarded parity probes; no new model is published.

## Complete-fight validation

Run the same 16 starts to combat completion, allowing up to 512 decisions and
1,800 seconds per episode. Repeat the initializer comparison three times with
alternating baseline/final order. Also compare the frozen 50k Search student once
in each implementation; that checkpoint uses the detached public-history view.

| Measurement | Baseline | Final |
|---|---:|---:|
| Initializer: median 16-fight batch | 59.69 s | 53.16 s |
| Initializer: batch range | 58.45–61.45 s | 52.11–53.86 s |
| Initializer: median searched-action latency | 2.11 s | 1.85 s |
| Initializer: searched-action p95 | 2.84 s | 2.40 s |
| Initializer: maximum searched-action latency | 3.71 s | 3.40 s |
| Student: one 16-fight batch | 58.57 s | 52.57 s |

The repeated complete-fight comparison uses **10.9% less wall time** (1.12×
throughput). Each paired repetition improves by 10.8–12.4%. The single student
pair uses 10.2% less time; it is a compatibility/performance cross-check, with less
timing evidence than the three-repetition initializer comparison.

All **128 executed fights** complete. Each initializer batch has 374 decisions,
301 searched decisions, 7,224 simulations and 24,464 leaf steps. Each student
batch has 370 decisions, 300 searched decisions, 7,200 simulations and 24,274 leaf
steps. There are no unsupported fallbacks, search cutoffs, time bootstraps or
unfinished fights. Full public trajectories, targets, values, visits, tree work,
outcomes, HP and potion use match exactly within each checkpoint. No searched
action exceeds five seconds on this panel. This is training-panel compute
validation, not a new held-out strength comparison.

Applying the measured complete-fight ratio and combined loader ratio to the
[previous 50k run](VANTOM_SEARCH_TRAINING_2026_10_08.md) gives a rough projection:
102.96 minutes of collection becomes 91.69 minutes, 16.45 minutes of preparation
becomes 11.71 minutes, and the 0.93-minute learner phase is held unchanged. Total:
**about 1h44m instead of 2h00m**, or roughly 16 minutes saved. This is an
extrapolation from the benchmark, not another measured 50k run. Dataset mix,
machine load and search behavior can change the realized speed.

## Evidence and validation

The local bundle is `runs/search-training-speed-20261008/`. It contains baseline
and variant sources, `ablation-protocol.json`, the extended `protocol.json`, exact
input bindings, repeated results, semantic fingerprints and `analysis.json`.
The pilot is retained separately and excluded from the reported medians.
Original training protocols, checkpoints and evidence remain unchanged.

One independent semantic review found and resolved cache-key type/equality
issues, custom-hook/structural-record compatibility, and catalog validation for
omitted feature rows. Its final source-bound review has no blockers. Focused
regressions cover those cases plus exact owner identity, capacity failures,
cache bounds, hidden draw/RNG independence, independent rollouts and optional
inference dependencies. Complete-fight measurements above and final integration checks below use the
reviewed production implementation.

Final integration: `tests/agent` plus `tests/test_package_layout.py` reported
1,659 passes, one skip and one sandbox-only failure in 621.95 seconds. The failed
trace-viewer test could not bind its ephemeral localhost socket; rerunning only
that test with the required permission passed in 0.63 seconds. Thus all 1,660
executed tests passed after the environment retry. Python compilation of `game`
and `tests` also passed. The earlier focused change suite passed 73 tests in
10.44 seconds; the broader run includes the final added regressions.
