# Direct search learning: input compatibility verification

Date: 2026-10-04. **Experimental; no promotion.** This milestone enables the
learning path that the [direct-sampling experiment](COMBAT_DIRECT_SAMPLING_2026_10_04.md)
left gated. The [training guide](../AGENT_TRAINING.md#experimental-combat-search)
owns usage; the [architecture](../COMBAT_SEARCH_ARCHITECTURE.md#learner-input-compatibility-stage-5-learning-slice)
owns the remaining design gates. This is controlled headless evidence, not native
bridge or campaign acceptance. The [evidence extract](combat_search_learning_2026_10_04.json)
retains exact report, source, checkpoint and public-artifact bindings.

## Implemented behavior

The shared `detached_combat_history_cards_v1` view removes ambiguous historical
card-to-current-copy links while retaining current cards, action candidates and
the original recorded public journal. Teacher inference, distillation features
and student inference use the same transformation. Feature identities, compact
rollouts and corpus identities bind the view; mixed-view learning batches reject.

Normalized students use inference bundle v4 with an explicit `input_view`.
Raw v1–v3 checkpoints retain their original semantics. New search reports and
targets use v2 with explicit `planning_view`; raw v1 training data remains
readable. Missing or conflicting direct-view provenance rejects. A raw teacher's
weights may initialize a normalized student with a fresh optimizer, with the
change recorded in the distillation report. The reverse transfer is rejected.

Reanalysis validates the original public anchor, records the new teacher/view,
and refreshes policy targets along the original actions. Original trajectory and
training-sidecar bytes stay unchanged. Completed-behavior returns remain the
critic labels; unfinished fights have no fabricated terminal labels. Reanalysis
does not become a new evaluation result. Ordinary PPO collects its own policy's
behavior and preserves the view through serial/workers, fingerprints and exact
resume; search targets never become PPO behavior probabilities.

Detaching old links can renumber an encoding's reference table. PPO therefore
checks environment arrays against the original public graph and requires the
policy to retain the same ordered current action references. It does not compare
unrelated numeric indexes from the two views or bypass action-mapping validation.

The old `commit_single_card_v1` restriction needs the historical selected-card
link, so direct search and normalized encoders/models explicitly reject that
pairing. The current specialist's `commit_decisions_v1` and
`commit_card_selection_v1` retain their current-state selector restrictions.
No restriction is silently widened. The direct model's existing content guards,
declared-start requirements and campaign/native exclusions remain in place.

## Bounded experiment protocol

Freeze the same compatible specialist as the previous panel:
`runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model`, SHA-256
`4f06f6566a83bf658685ddbf799e0e4c2856d00eb979a7b7d35b890c25562595`.
The unshaped objective remains victory plus 0.1 times winning HP fraction after
cleanup; defeat is zero. No held-out data is opened.

Collect eight training starts at indices 400–407 in the frozen encounter order:
Nibbit, Slimes, Bygone Effigy, Vantom, Corpse Slugs weak, Living Fog, Skulking
Colony and Lagavulin Matriarch. Use 16 simulations, depth 16, two particles,
1,024 conditioning proposals, 2,048 recovery proposals, 16,384 replay steps,
five-second thinking/belief ceilings, 48 decisions and 90 seconds per episode,
with four workers. Freeze the teacher throughout collection.

Run 16 distillation updates at the existing learning rate 0.0001 and batch size
32, seed zero. Evaluate both its unchanged-weight normalized initializer and the
resulting student on validation indices 200–207, pairing normalized greedy,
root-only and Gumbel policies with the same search budgets and four workers.
The initializer comparison was added before opening the student's results, to
keep the before/after comparison on the same implementation. Reanalyse the eight
original training trajectories with that student at 16 simulations, following
the original recorded actions.
This small round verifies operation and compatibility; it is not training-scale
selection, evidence of a stronger teacher, or authorization for automatic promotion.

## Results

Collection completed **eight fights: five wins and three defeats**, with 157
reconciled actions. All **115 non-forced decisions** completed their 16 search
simulations; 42 forced decisions were excluded from distillation. There were no
belief fallbacks, episode cutoffs or operational failures. The resulting corpus
contains 115 probability targets and 115 actual completed-return labels.

The initializer retains the original teacher's exact weights. Its predictions
match the teacher on normalized inputs at **all 157 recorded decisions**.
The student completed 16 updates and saved a v4 checkpoint with the detached
view and unchanged `commit_decisions_v1` restriction. Across the same complete
training corpus, search-target cross-entropy fell from **0.9209 to 0.8522** and
value MSE from **0.1639 to 0.1161**. These measure training fit, not generalization.

| Development controller | Initializer wins | Student wins | Initializer mean winning HP | Student mean winning HP |
| --- | ---: | ---: | ---: | ---: |
| Normalized greedy | 6 / 8 | 6 / 8 | 55.33 | 56.83 |
| Root-only simulation | 6 / 8 | 6 / 8 | 57.33 | 56.00 |
| Gumbel | 6 / 8 | 6 / 8 | 54.50 | 55.50 |

Both development panels completed every fight with no cutoff or failure. The
student's Gumbel controller searched **112/112 non-forced decisions**, plus 41
forced decisions. Its largest per-fight p95 action duration was **0.330 seconds**
at 16 simulations, versus 0.316 seconds for the initializer. There were no
belief fallbacks. All six controller/checkpoint combinations won and lost the
same encounters; every paired win difference is zero. The conservative grouped
95% interval is **[−96.0, +96.0] percentage points**. This panel establishes no
credible strength gain, and the conditional HP differences do not change that
conclusion. No student was promoted and no held-out test was opened.

Reanalysis refreshed all **115 searched distributions** along the eight original
training fights. Fourteen recommended actions changed. The original trajectory
and training-sidecar bytes, public planning anchors/completions, behavior policy
identity and every completed-return label remained unchanged. Those fourteen
recommendations were not substituted for recorded behavior or scored as newly
played fights. All 42 forced positions remained forced; no belief fallback or
replay recovery was needed.

The local report directories are:

- `runs/direct-search-learning-collect-20261004/`
- `runs/direct-search-learning-student-20261004/`
- `runs/direct-search-learning-initial-eval-20261004/`
- `runs/direct-search-learning-student-eval-20261004/`
- `runs/direct-search-learning-reanalysis-20261004/`

They represent 56 actual fight executions and eight reanalysed records, not 64
new fights. The extract verifies all 64 records and 918 per-decision target
entries. Historical evidence files and implementation identities were preserved.

Reported execution times on the local arm64 Mac (macOS 26.6.2, Python 3.11.15,
one Torch thread per worker) were 10.87 s for collection, 16.93 s for initializer
evaluation, 17.38 s for student evaluation and 26.01 s for serial reanalysis.
Distillation's timed update/final-publication phase took 0.22 s. These are the
existing report timers, not complete CLI process timings. Experiments ran
sequentially without a simultaneous test/reviewer workload.

## Validation and reproduction

The final author aggregate passed **292 tests in 124.92 s**, covering views,
search learning, checkpoint compatibility, actor features, serial/parallel PPO,
action restrictions, full-run consumers, tracking and search/belief regressions.
An additional runner/package/checkpoint-tracking/CPU suite passed **42 tests in
40.64 s**. Compileall and whitespace checks passed. Artifact verification checked
the source/checkpoint/teacher/view bindings, actual legal action mappings,
normalized distributions, completed returns and immutable reanalysis outcomes.

One independent semantic review found no remaining blockers. Its final input-view
suite passed **21 tests in 6.85 s**. Independent actual-selector fixtures confirmed
that supported commitment policies retain their restrictions. Review and author
checks identified and fixed the original-graph PPO comparison and incompatible
history-dependent restriction described above; reverse detached-to-raw
distillation now also rejects before creating output artifacts.

The existing commands reproduced the full workflow, invoked locally through
`PYTHONPATH=. .venv/bin/python -m game.cli.agent_train` or
`game.cli.agent_evaluate`. Use fresh output directories. For example, after
collection with the frozen protocol above:

```bash
sts-agent-train search-distill \
  --checkpoint runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model \
  --training-report runs/direct-search-learning-collect-20261004/search.json \
  --output-dir runs/direct-search-learning-student-repeat --updates 16 --seed 0

sts-agent-train search-reanalyse \
  --checkpoint runs/direct-search-learning-student-repeat/final.sts-model \
  --training-report runs/direct-search-learning-collect-20261004/search.json \
  --search-model direct_belief_v1 --search-simulations 16 --search-depth 16 \
  --search-seconds 5 --belief-particles 2 --belief-proposals 1024 \
  --belief-replay-proposals 2048 --belief-replay-steps 16384 --belief-seconds 5 \
  --output-dir runs/direct-search-learning-reanalysis-repeat
```

The collection command uses `search-collect --cases 8 --start-index 400
--workers 4 --max-decisions 48 --time-limit 90`, the same search/belief flags,
and one `--encounter` for each listed encounter in order. Evaluation uses
`sts-agent-evaluate --search --search-cases 8 --start-index 200
--split validation` with the same encounters/budgets, separately for
`initial.sts-model` and `final.sts-model`.

Separate implementation and review wall-time totals were not retained. No native
build, package, installation, live-data access or user setup wait was required.
The next gate is a frozen paired combat-benefit experiment and critic diagnosis
before scaling training. Broader content, campaign anchors and native bridge
support remain separate milestones; default search promotion still requires the
positive paired Act 1 confidence gate.
