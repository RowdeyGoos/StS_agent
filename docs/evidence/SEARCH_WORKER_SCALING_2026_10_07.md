# Search worker scaling and observation cost — 2026-10-07

**Sixteen independent fight workers gave 2.10× the throughput of four.** A separate
compact-encoding prototype reduced encoding time by 47.7% and complete search time
by 29.9% on six opening positions, preserving exact features and search results.

Use 16 workers for throughput on this workload; 12 is a reasonable option when
leaving more capacity for other work, at approximately 7% longer batch time. The
next implementation priority is the compact inference path. Its integration and
combined throughput at 16 workers remain to be measured.

## Worker results

Each entry summarizes three complete runs of the same 42 Vantom fights.

| Workers | Median batch | Observed range | Speedup over 4 | Search-action p95 |
|---:|---:|---:|---:|---:|
| 4 | 6:39 | 6:31–6:41 | 1.00× | 3.03s |
| 8 | 4:07 | 4:03–4:11 | 1.62× | 3.39s |
| 12 | 3:23 | 3:21–3:23 | 1.96× | 3.74s |
| 16 | 3:10 | 3:03–3:14 | 2.10× | 4.21s |

Latency is search plus public conditioning, excluding actual game execution and
recording; the table reports the median of each trial's p95. At 16 workers the
median search latency was 3.49s, and throughput was 3.20 searched decisions/s or
13.29 completed fights/minute. Extra workers improve batch throughput while
increasing individual-action latency.

All **504 fights** completed with matching public trajectories, outcomes, search
targets, action values, visits and work. Each batch had 1,224 real decisions, 606
searched decisions and 14,544 simulations. There were no execution failures, game
cutoffs, search cutoffs or belief-budget fallbacks. Every searched decision finished
24 simulations. All batches reproduced the original study's 26/42 wins, HP,
returns and potion use. These are performance repetitions, not new win-rate evidence.

The five-second target is not a hard guarantee: 6 of 1,818 searched actions at 16
workers exceeded five seconds, with a maximum of 6.56s. The corresponding counts at
4/8/12 workers were 1/3/6. These runs used generous ceilings to preserve fixed work;
applying a strict five-second cutoff requires its own evaluation. Collection should
keep a generous safety timeout separate from the fixed simulation budget.

Summed per-worker resident-memory high-water marks were approximately 1.25, 2.49,
3.67 and 4.80 GiB for 4/8/12/16 workers. These sums exclude the parent process and
are **not measurements of simultaneous memory use**. Finite-batch startup and the
tail of longer fights also limit scaling; a much larger collection has not been
benchmarked here.

## Question and controlled work

Compare 4, 8, 12 and 16 independent fight workers on this Mac. Each worker owns one
frozen Vantom specialist and one Torch compute thread, with a fresh engine, search
owner and seeded RNG for every fight. This measures search collection/evaluation
throughput; it does not distribute one search tree across workers.

Use all 42 previously used validation openings from the
[Vantom comparison](VANTOM_SPECIALIST_SEARCH_2026_10_07.md), the same checkpoint and
reviewed experimental opening adapter. The search configuration remains 24
simulations, four leaf rollout actions, depth 16 and two belief particles. No
learning, new outcome evaluation set, held-out access or policy promotion is part
of this measurement.

The only planner limit change is a 120-second action/conditioning ceiling, allowing
every worker configuration to finish exactly the same fixed work. The five-second
play target is measured separately; reducing work under contention must not appear
as a throughput improvement. Episode limits remain 512 actions and 1,800 seconds.

Three repetitions run serially, in worker-count orders 4/16/8/12, 12/8/16/4 and
8/4/12/16. No profiling or other experiment CPU jobs run alongside timed batches.
The order varies but does not eliminate thermal or unrelated host-load effects.
Timing includes pool/model startup, restored-start verification, gameplay,
recording, diagnostics, trajectory hashing and pool teardown. These are batch
timings, not pure warm-worker steady-state throughput.

Require identical public action/observation trajectories, search targets, values,
visits, simulation and leaf work, fallback coverage and completed outcomes. All
searched actions must finish 24 simulations without a timed leaf bootstrap. Any
belief-budget fallback invalidates the fixed-work comparison. Timing repetitions
are not independent win-rate evidence.

## Observation and encoding probe

After the worker sweep, separately measure six fixed opening positions and their
simulated public descendants. Split the existing inference timer into public
packing/validation, learned feature extraction, tensor collation and neural-network
execution. Keep profiler measurements separate from unprofiled speed comparisons.

Two experiment-local alternatives retain the frozen network and its exact inputs:

1. Fresh `PreparedPublic` validation followed by the existing record packer.
2. Fresh `PreparedPublic` validation and a compact mapping pass, omitting lossless
   tensor tables the actor does not read. Learned feature extraction stays the same.

The compact probe preserves capacity checks, public reference interning, candidate
ordering and policy masks. Structurally matching custom records use the existing
encoder to preserve their wire traversal order. Neither probe replaces the public
wire contract, recording or the bridge boundary. Production code is unchanged.

The six fixed case indices were 0, 7, 14, 21, 28 and 35. Across three timing
repetitions, every variant matched the original complete search result exactly.
Checks also compared all learned features, candidate/reference mappings, tensor
inputs and network outputs on 96 simulated observations, plus 39 ownership,
capacity, terminal, custom-record and reference/candidate permutation cases.

| Inference path | Encode 96 observations, median | Six searches, median | Search time reduction |
|---|---:|---:|---:|
| Current | 0.822s | 12.635s | — |
| Fresh prepared owner + existing packer | 0.828s | 12.355s | 2.2% |
| Fresh prepared owner + compact mapping | 0.430s | 8.856s | 29.9% |

The compact variant's search speedup was 1.42–1.45× in the three paired repetitions.
Fresh ownership/validation and capacity checking are included in its timing; it
does not obtain the gain by trusting unchecked records. Creating a fresh prepared
owner while still building all lossless arrays gave no encoding-only improvement
on this panel and only a small total-search gain.

Separate unprofiled instrumentation across 726 network-provider calls measured:

| Component | Share of measured search wall time |
|---|---:|
| Public packing, including wire conversion and validation | 44.3% |
| Public-state projection | 29.3% |
| Learned feature extraction | 10.8% |
| Hypothetical-world sampling | 5.2% |
| Neural network and probability/value output | 4.7% |
| Engine rule transitions | 2.2% |
| Tensor collation | 0.3% |

The remaining time covers reconstruction, tree bookkeeping and other overhead.
Projection itself includes public preparation/validation, so the packing category
does not contain every validation cost. This is a serial six-position measurement;
it is not a claim that every combat has the same proportions.

The separate `cProfile` run supports this diagnosis: repeated wire traversal,
parsing and packing dominate. Of the 8.79 inclusive profiler seconds inside
`FullProjection.decision`, 4.16 were inside `PreparedPublic` construction. Card
signature serialization and combat-channel extraction are further candidates.
Inclusive profile times overlap and include profiler overhead; they are not the
wall-time percentages in the table above.

## Recommended implementation order

The next changes should preserve search work and model inputs:

- Give inference a learned-feature path that returns the existing compact rollout
  representation and exact candidate correspondence, without constructing unused
  lossless tables. Retain full public encoding for recording and consumers that
  actually need it.
- Carry the existing validated public owner through compatible in-process steps.
  Reusing an owner is valid only for its exact immutable observation; applying a
  history view or strategic-context overlay creates a different observation that
  must receive its own validated owner.
- Reuse immutable public card-spec/mechanic descriptions across projections and
  extract only present combat channels. Keep current costs, powers, modifiers,
  positions and physical-copy correspondence dynamic. A cache of an entire public
  observation is not the same optimization; the earlier study found that approach
  slower on its panel.

These opportunities fit the future bridge because their input is the validated
public observation. They do not require a private-state shortcut, new game rules,
a different critic objective or additional action pruning. Model batching across
workers is a later measurement candidate if neural execution remains a material
cost after the Python-side work is reduced.

## Evidence and validation

The independent semantic review covered worker/RNG ownership, cleanup, semantic
equality, public ownership and compact-mapping ordering/capacity checks. Startup
cleanup and the encoding probe's terminal/custom-record compatibility findings were
fixed before their respective measurements.

The corrected runtime probe passed all checks above. Its initial preflight stopped
because a custom-record test fixture lacked the accessor required by the existing
feature encoder; the fixture was corrected before any accepted probe timing. The
worker benchmark was unaffected. No engine, production search, training or bridge
source was changed by this experiment.

The worker sweep took 3,104.57 seconds (51.74 minutes); the corrected encoding and
profiling run took 169.15 seconds. Implementation and review overlapped and were
not separately timed. Runtime: macOS 26.6.2 arm64, 18 available CPUs, Python 3.11.15,
Torch 2.13.0 and NumPy 2.4.6, with one Torch thread per worker.

- [Frozen worker protocol](../../runs/search-worker-scaling-20261007/protocol.json)
- [Worker harness review](../../runs/search-worker-scaling-20261007/review.json)
- [Encoding probe review](../../runs/search-worker-scaling-20261007/encoding-review.json)
- [Machine-readable results and source bindings](search_worker_scaling_2026_10_07.json)
- [Full timing analysis](../../runs/search-worker-scaling-20261007/analysis.json)
- [Encoding measurements and profile](../../runs/search-worker-scaling-20261007/overhead.json)
- Local bundle: `runs/search-worker-scaling-20261007/`

The prior study's exact production source archive and accepted adapter tests remain
bound through the new protocol. Raw trial reports, public trajectories, protected
audit files and per-action search diagnostics remain in the local bundle.
