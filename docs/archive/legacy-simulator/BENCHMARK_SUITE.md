# Full-System Benchmark Suite

> Archived 2026-09-22: this pipeline is retired. Commands and source descriptions
> apply to the original revision, not the current engine.

`sts-benchmark-suite` runs the controlled multi-model campaign described by
`configs/full_system_benchmark_balanced.json`. It is separate from
`sts-benchmark`: the existing command evaluates already-saved policies, while
the suite trains, selects, evaluates, inventories, and reports a complete
experiment.

## Fairness Model

The primary leaderboard gives every trainable policy the same number of
environment transitions. Those runs may execute in three independent processes
because contention changes elapsed time, not training experience.

The time-to-result leaderboard is secondary. It reruns only the four confirmed
finalists, one at a time, for 900 active training seconds. Evaluation and
artifact serialization are outside that timer. The run records both the timer
cutoff and the precise elapsed time of the retained optimizer state; an update
that crosses the cutoff is rolled back. Historical checkpoints retain their
original budgets and never enter either controlled leaderboard.

## Running The Campaign

Inspect the complete resolved matrix without writing artifacts:

```bash
sts-benchmark-suite --dry-run
```

Run or resume the balanced campaign:

```bash
sts-benchmark-suite
```

The default output is `benchmarks/suites/full-system-balanced`. Every training
cell has a deterministic run ID, checkpoint, resolved config, run metadata,
log, and completion marker. Evaluation is stored per checkpoint/deck/encounter,
so interruption does not invalidate completed cells. Rerunning the command
resumes them by default.

Run a fast smoke campaign:

```bash
sts-benchmark-suite --mini --output-dir benchmarks/suites/smoke
```

The mini campaign omits the inherently throughput-dependent equal-time and
oracle stages. It is intended for deterministic integration checks, not model
quality conclusions.

Individual stages can be resumed after their prerequisites exist:

```bash
sts-benchmark-suite --stage confirmation --stage time --stage report
```

## Controlled Matrix

The production manifest screens 13 trainable variants on the starter and
Ironclad sequencing decks:

- Q-learning
- DQN, Double DQN, and Dueling Double DQN using `flat`, `action_feature`, and
  `shared_enemy`
- Masked PPO using the same three architectures

Screening uses 32,768 transitions and seed 7. Four finalists are confirmed with
65,536 transitions across seeds 7, 1007, and 2007. Three confirmed variants are
then retrained from scratch on `overgrowth_hard_v1`. Every saved policy is tested
on both decks and all seven fixed multi-enemy encounters using the common combat
seed list 100000 through 100099.

## Outputs

The suite produces:

- `manifest.resolved.json`
- `checkpoint-inventory.json`
- raw per-episode JSONL
- per-stage JSON and CSV rankings
- model resource and card-encoding microbenchmarks
- explicit simple-environment sanity results
- finalist selections
- bounded oracle diagnostics
- `summary.json`
- `report.md`

The robust ranking orders macro win rate first, then the worst deck/encounter
cell, damage taken, remaining HP, reward, and stable variant name. The Markdown
report and JSON include Wilson win-rate intervals, training-seed spread, paired
combat-seed differences, easy/hard and deck-transfer views, hard-vs-easy-pool
comparisons, throughput, checkpoint/model size, and batched inference latency.

`card_records_v1` is measured for extraction, tensorization, inference cost,
memory, gradients, invariance, and append-only dimension stability. It is not
connected to policy training, so the suite deliberately does not assign it a
win rate.
