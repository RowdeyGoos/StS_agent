# Vantom: replay and selective reanalysis — 2026-10-08

This fixed development experiment compares two more epochs on saved Search
targets against the same training with a subset refreshed by the 150k network.
**No fresh training game decisions were collected.** Both students remain at
150k cumulative fresh decisions; replay presentations and hypothetical Search
simulations are reported separately.

## Matched validation

| Controller | Wins | Win rate |
| --- | ---: | ---: |
| 150k baseline, network | 22/42 | 52.4% |
| 150k baseline + Search | 28/42 | 66.7% |
| 150k + replay, network | 22/42 | 52.4% |
| 150k + replay + Search | 26/42 | 61.9% |
| 150k + selective reanalysis, network | 24/42 | 57.1% |
| 150k + selective reanalysis + Search | 24/42 | 57.1% |
| 250k PPO specialist, network | 26/42 | 61.9% |
| 250k PPO specialist + Search | 28/42 | 66.7% |

The original 150k controller remains strongest with Search in this trial.
Plain replay leaves the network-only win count unchanged and loses two net
Search wins. Selective reanalysis adds two network-only wins over replay but
loses two further Search wins. Its Search controller loses four of the baseline's
wins and gains none. Neither candidate is promoted.

This tests two extra passes over the latest 50k collection, with only 3,299 of
39,667 targets refreshed (8.3%). It does not establish that replay or reanalysis
is generally ineffective. The reason for the Search regression is not isolated
here; comparing value estimates and decision traces on the lost fights is the
next diagnostic before scaling either training recipe.

| Paired comparison | Difference | 95% paired campaign bootstrap |
| --- | ---: | ---: |
| 150k + replay + Search versus 150k baseline + Search | -4.76 pp | [-14.29, +4.76] pp |
| 150k + selective reanalysis + Search versus 150k + replay + Search | -4.76 pp | [-11.90, +0.00] pp |
| 150k + replay, network versus 150k baseline, network | +0.00 pp | [-9.52, +9.52] pp |
| 150k + selective reanalysis, network versus 150k + replay, network | +4.76 pp | [+0.00, +11.90] pp |
| 150k + selective reanalysis + Search versus 150k baseline + Search | -9.52 pp | [-19.05, -2.38] pp |

All four candidate controllers completed the same 42 known validation openings,
giving 168 newly played evaluation fights without failures or cutoffs. The four
baseline/PPO controllers reuse 168 source-identical round-3 fights: checkpoint,
source, toolchain, public starts, analysis seeds, budgets and artifact bindings
were verified. These reused fights are not counted as new evidence.
Intervals use 20,000 fixed-seed paired source-campaign resamples. Secondary
comparisons are descriptive. These are repeatedly used development cases;
all 57 held-out fights remain unopened. No default promotion or Act 1 claim is made.

## Data reuse and controlled difference

Both students initialize exactly from the [150k checkpoint](../../runs/vantom-search-round3-20261008/student/final.sts-model),
SHA-256 `7805954e02238a6928a3c15ce2b6d65e492f1743a3a1bb87054dc8ffa5d9c9b0`. Each uses the latest round's 50,000 recorded decisions,
containing 39,667 searched examples across 2,308 episodes. Earlier rounds are not
added to this trial. Each arm runs two extra epochs: 79,334 presentations and
2,480 updates. Adam starts fresh in each arm; batch 32, learning rate 0.0001,
value weight 0.25, gradient clip 1 and learner seed 2026100804 are identical.

- **Replay:** use the saved 100k-teacher Search targets unchanged.
- **Selective reanalysis:** replace only policy targets for 202 preselected episodes:
  one opening and one continuation for each of the 101 training source fights.
  Selection uses a fixed seed and no outcomes. The frozen 150k network refreshes
  4,154 recorded decisions, including 3,299 searched choices.
  Search settings and each episode's analysis seed stay exactly as originally recorded.

Reanalysis changed 3,299 action distributions and
619 most-probable actions. Mean total-variation distance from
the old distribution is 0.167597. These changes are
new training advice, not newly observed wins or losses.

All original public trajectory and reward sidecar bytes, reveal receipts,
completion records, accepted behavior actions and outcome provenance remain
unchanged. Original transition indices match exactly. There are still 38,784
completed-return value labels and 883 missing labels from truncated fights.
Only policy probabilities change; features, candidate mappings, actions, critic
labels and minibatch order match exactly between arms. Refreshed examples replace
old targets in place and are not duplicated. No searched data enters PPO.

The experiment loads the original validated corpus once and uses existing
`ImitationLearner`, `ActorCritic` and checkpoint serialization for both arms.
Refreshed corpora are independently validated before replacement; every feature
field/array, action, value label and retained transition index is compared.
Shared preparation saves repeated loading while preserving the matched test.
There is no production algorithm change or new general replay service.

## Work and validation

Reanalysis uses 16 workers with one Torch thread each; training uses four threads.
Search retains 24 simulations, depth 16, four greedy leaf actions, two belief
particles and the existing 120-second ceilings. All eligible refresh and searched
validation choices complete their fixed budgets without unsupported fallbacks,
Search cutoffs or timed leaf bootstraps. The unshaped combat win/HP objective is unchanged.

| Phase | Measured wall time |
| --- | ---: |
| Selective reanalysis | 7.34 min |
| Shared data preparation and correspondence audit | 13.44 min |
| Replay optimization and checkpoint work | 48.81 s |
| Refreshed optimization and checkpoint work | 47.25 s |
| Four candidate validation controllers | 4.70 min |

The two-episode smoke refreshed 33 searched decisions and validated outcome/history
preservation; smoke outputs are excluded from learner inputs. Two focused existing
tests passed for combined-report/epoch accounting and observed-receipt reanalysis.
Broader accepted production evidence is reused because production source is unchanged.
One independent semantic review closed without blockers. Final audits verify
original initialization tensors, identical minibatch order, normalized legal
targets, unchanged critic labels, all source bindings and complete evaluation.
No release or installation was involved; separate review/preparation elapsed
times were not recorded.

## Artifacts

- [Machine-readable evidence](vantom_search_reuse_2026_10_08.json)
- [Frozen protocol](../../runs/vantom-search-reuse-20261008/protocol.json)
- [Selection manifest](../../runs/vantom-search-reuse-20261008/selection.json)
- [Reanalysis report](../../runs/vantom-search-reuse-20261008/reanalysis.json)
- [Corpus correspondence audit](../../runs/vantom-search-reuse-20261008/corpus-audit.json)
- [Full matched evaluation](../../runs/vantom-search-reuse-20261008/evaluation.json)
- [Replay student](../../runs/vantom-search-reuse-20261008/replay/final.sts-model), SHA-256 `f3d776b39584cf5e89fc80a6aaa891cc1db3f99a7e2402cd5971503a94bf17a0`
- [Selective-reanalysis student](../../runs/vantom-search-reuse-20261008/refresh/final.sts-model), SHA-256 `3ee53a212814915b48b40c3d68c0a925030539f7e691ab344eee1e08d7330092`
- [Experiment driver](../../runs/vantom-search-reuse-20261008/reuse.py)

Both learners and the comparison are recorded in the existing local **Vantom
search 50k** experiment with **150k sample reuse** names. Candidate Search traces
remain available under this bundle's `evaluation-*_search/` directories.
