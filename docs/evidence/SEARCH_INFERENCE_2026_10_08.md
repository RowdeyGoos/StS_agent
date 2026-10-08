# Production search inference optimization — 2026-10-08

**The combined change reduced complete search-batch time by 35.4% at 16 workers,
with identical decisions and search results.** The compact inference prototype is
now part of checkpoint inference. Combat features also skip absent channels when
filling the existing numeric arrays. On the six-position serial panel, complete
search time fell 33.1% and encoding time fell 58.4%.

## What changed

`CheckpointPolicy` uses `FeatureEncoder.encode_inference()` and the existing
compact `RolloutFeatures`. Each inference validates a fresh public owner and
checks the same capacities, but does not construct unused lossless arrays. Full
encoding and compact mapping share one traversal and one candidate-ordering
implementation. Structural caller records and custom encoder hooks retain the
ordinary path so their reference ordering and calling conventions stay intact.

Combat channel extraction visits present values instead of scanning every
possible channel for every node. It retains the same numeric transformation,
array layout, known-zero flags and unknown values. Both changes preserve
checkpoint/feature identities, masks, public recordings and search work. They
apply automatically when existing checkpoints perform inference. Game rules,
public-information access and RNG ownership do not change.

## Controlled comparison

Reuse the 42 validation openings, specialist checkpoint and guarded experimental
adapter from the [worker benchmark](SEARCH_WORKER_SCALING_2026_10_07.md). Each
trial uses 16 spawned workers with one Torch thread each, 24 simulations per
searched decision, four leaf actions, depth 16 and two belief particles. Action
and conditioning ceilings are 120 seconds so reduced work cannot masquerade as
improved performance. Episode limits remain 512 decisions and 1,800 seconds.

Run three paired timing repetitions in order: legacy/optimized,
optimized/legacy, legacy/optimized. The legacy arm loads the saved pre-change
checkpoint-policy, feature-encoder, full-encoder and dense-channel sources into
the same current search/engine build. Both arms share the semantically unchanged
public codec, including the extracted candidate-ordering helper. The harness
loads both inference implementations in each worker and selects one for its
lifetime. Timings include worker/model startup, restored-start verification,
gameplay, recording, diagnostics, hashing and shutdown.

Before timing, verify the frozen checkpoint, corpus/registry and all 42 admitted
private snapshots against their recorded hashes and public opening digests.
The planner still receives only public observations. Frozen source bindings and
freshness checks reject changed implementations; old protocols and evidence
remain unchanged. No held-out positions are opened. No profiling or other
experiment CPU work runs alongside timed batches.

## Full-fight results at 16 workers

Each entry summarizes three complete runs of the same 42 validation fights.

| Measurement | Legacy | Optimized |
|---|---:|---:|
| Median batch time | 3m40.1s | 2m22.3s |
| Observed batch range | 3m35.2s–3m42.6s | 2m21.0s–2m22.3s |
| Searched decisions per second | 2.75 | 4.26 |
| Median search-action latency | 3.86s | 2.42s |
| Search-action p95 | 4.57s | 2.89s |
| Search actions exceeding five seconds | 25/1,818 | 3/1,818 |
| Maximum search-action latency | 7.28s | 5.54s |

Latency includes search and its public belief update, excluding actual game
execution and recording. Median/p95 entries are the medians of the three
trial statistics. The optimized throughput is **1.55×** the baseline; the three
paired speedups were 1.564×, 1.527× and 1.547×. Compare these paired timings;
absolute baseline times differ from the earlier worker study's host session.

All **252 replayed fights** completed. Every batch reproduced the earlier
benchmark's exact public trajectories, search targets, values, visits, work and
outcomes: **1,224 real decisions, 606 searched decisions, 14,544 simulations,
249 forced actions and 369 unsupported-scope fallbacks**, with 26/42 wins.
There were no failures, episode cutoffs, search cutoffs, timed leaf bootstraps or
belief-budget fallbacks. Remaining HP, returns and potion usage also matched.
Thus the performance gain did not come from reducing coverage or simulated work.

Summed worker resident-memory high-water marks had medians of 4.80 GiB before
and 4.73 GiB after. They exclude the parent and are not simultaneous memory
measurements; both arms loaded the same benchmark-only comparison machinery.
The five-second target still has exceptions even on this workload.

## Serial encoding and search

Six fixed opening indices (0, 7, 14, 21, 28, 35) generate 726 network-provider
calls. Ninety-six sampled public descendants match the archived implementation
exactly: feature arrays including combat channels, action correspondence, legal
and policy masks, tensor inputs, probabilities and critic values. This compares
the sparse channels against the saved dense implementation, not just two callers
of the new code.

Three timing repetitions compare the legacy path, compact encoding with the old
dense channels, and production compact encoding with sparse channels:

| Inference path | Encode 96 observations, median | Six searches, median |
|---|---:|---:|
| Legacy | 1.004s | 14.203s |
| Compact encoding only | 0.474s | 9.982s |
| Compact encoding + sparse channels | 0.418s | 9.506s |

The combined encoding-time reduction is 58.4%; complete-search time falls 33.1%.
Sparse extraction adds an 11.9% encoding-time reduction and a 4.8% search-time
reduction beyond compact encoding. Every timed search matches its legacy result,
including target probabilities, values, visits and simulation/leaf work.
Fresh ownership validation and capacity checks are included in timing.

In the third optimized repeat, the six searches took 9.459 seconds. Existing
unprofiled timers attributed 4.235 seconds to inference (including encoding),
3.843 to public projection, 0.593 to world sampling, 0.326 to rule transitions
and 0.109 to reconstruction. The remainder is tree/bookkeeping work. Public
projection now accounts for about 41% of this panel's wall time.

A separate profiler run shows repeated public validation and card-signature
serialization inside those costs: 1,834 `PreparedPublic` constructions across
1,108 projections and 726 inference calls, plus 34,489 card signatures. Profile
times include instrumentation overhead and nested calls overlap; they are not
additional wall-time shares. The next optimization candidates are carrying an
already validated owner through compatible consumers and reusing immutable
public card descriptions. Each needs its own ownership and dynamic-field tests.

## Validation and scope

The stable-source affected suite passed **464 tests in 69.95 seconds**. It covers
v1/v2 encoding, all seven checkpoint representations and both public input views,
custom record and encoder compatibility, ownership, malformed records, competing
capacity failures, renamed physical references, candidate permutations, training
and checkpoint consumers, and search/belief integration. An independent semantic
review found and then cleared an instance-hook compatibility issue. The final
review has no blockers; the reviewer did not claim to execute the runtime checks.

An initial suite overlapped the hook correction and returned one `ValueError` in
spawned collection. That focused check passed on rerun, followed by the complete
stable-source run above. Only the latter is the accepted integration matrix.

These are performance repetitions of previously used validation fights, not new
win-rate evidence. Search coverage remains the guarded opening adapter's partial
coverage. Native bridge/campaign readiness and search-teacher strength are
separate gates. Generous ceilings establish fixed work; they do not prove a hard
five-second limit under arbitrary host load.

The retained bundle is `runs/search-inference-20261007/` (named when this work
started on October 7; measurements finished after midnight in Europe/Madrid).
It contains the pre-change sources, frozen protocol, reviewer result, stable
validation output, serial measurements/profile and per-fight diagnostics.
The [machine-readable summary](search_inference_2026_10_08.json) binds these
artifacts and records individual trials. The six timed batches took 18m03.5s
in total; the serial parity/timing/profile probe took 148.9s. Implementation and
review elapsed times were not measured separately. No native release or user
setup was required.
