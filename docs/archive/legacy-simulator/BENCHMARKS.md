# Fixed-Seed Policy Benchmarks

> Archived 2026-09-22: this pipeline is retired. Commands and source descriptions
> apply to the original revision, not the current engine.

`sts-benchmark` compares the built-in random and heuristic policies with any
number of labeled saved agents. Every policy is evaluated against the same
explicit fixed encounters and contiguous combat-seed sequence.

```bash
sts-benchmark \
  --encounter nibbit \
  --encounter slimes \
  --deck ironclad_sequencing \
  --episodes 100 \
  --seed 1000 \
  --agent ddqn=runs/double-dqn/example-run \
  --agent ppo=runs/masked-ppo/example-run \
  --device cpu \
  --json-out benchmarks/fixed-seeds.json
```

The random and heuristic policies are always included. `--agent` accepts a
unique display label followed by either a checkpoint file or a standard run
directory. The checkpoint type is detected automatically.

Benchmark JSON format version 2 requires the resolved named deck in
`config.environment.deck`. Reports using version 1 implicitly used `starter`.
The selected deck is fixed for the complete command; sampled deck sets remain a
future feature.

For `--episodes 100 --seed 1000`, every policy/encounter pair uses seeds 1000
through 1099. Saved-agent tie-breaking is reset for every encounter so changing
the encounter order cannot change a result. The terminal table shows win rate,
remaining HP, damage taken, reward, and step count. Reports created before
damage reporting is available display `0.00` in that column. The optional
versioned JSON preserves the complete `EvaluationStats.as_dict()` payload for
later tooling.

Only fixed encounter names are accepted. The sampled `overgrowth_easy` and
`overgrowth_hard_v1` pools are intentionally excluded because a per-encounter
comparison should not mix matchups inside one table row. The command obtains
its choices from the shared fixed-encounter registry.

Saved agents must match each selected environment's observation and action
layouts. In particular, a checkpoint trained with the three-enemy encoder is
not compatible with the single-enemy `simple` layout. All checkpoint and layout
checks complete before evaluation begins or a JSON file is created.
Shared-enemy neural checkpoints additionally preflight the complete enemy and
target-feature layout. A different training deck is not itself an error: the
benchmark permits cross-deck evaluation whenever those dimensions and layouts
match.
