# Public-information combat search: implementation and development pilot

Date: 2026-10-04. **Experimental; no promotion.** This records synthetic rule
checks, controlled combat experiments and genuine headless campaigns. It does
not establish live-game performance or broad Act 1 reconstruction coverage.
Usage and supported content belong to the
[training guide](../AGENT_TRAINING.md#experimental-combat-search).

## Delivered behavior

- A reconciled public observation/action/successor history and a restricted
  reconstruction model over the existing headless engine. Simulations receive
  independently seeded worlds built from public facts, never a sanitized copy
  of the actual private state. Known Headbutt placements survive draws, including
  duplicate cards. Pending selectors are reconstructed from the public prefix.
- An observation-history tree with Gumbel root selection, sequential halving,
  completed-value policy targets and the corresponding non-root selection rule.
  The last two candidates compete until the budget is spent. Enemy behavior is
  a chance transition; value backups retain their sign. The same checkpoint
  supplies priors, the combat critic and explicit fallback decisions.
- Opt-in play and paired combat/campaign evaluation, fixed simulation budgets,
  separate search/episode deadlines, independent episode workers, phase timing,
  public combat completion metrics and distinct experiment-tracking identities.
- Frozen-teacher collection, probability-target imitation, completed-outcome
  value labels and reanalysis with original behavior/outcome provenance.
  Truncations do not acquire terminal value labels. Search data does not enter
  the existing on-policy PPO collector. Students remain separate checkpoints.

The intended mechanics are covered by focused fixtures: card ordering, lethal
and survival choices, draw order, reshuffling, multiple enemy slots, potions,
selectors, powers, timed debuffs, enemy turns and combat cleanup. The supported
enemy roster spans Vantom and selected Overgrowth/Underdocks ordinary enemies.
Three simple Neow pickup relics also have reconstruction/cleanup checks. This is
an explicit content subset; unsupported inventory and history fall back.

## Frozen experiment

The teacher was the existing Vantom specialist's chunk-15 checkpoint:

`runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model`

Checkpoint SHA-256:
`4f06f6566a83bf658685ddbf799e0e4c2856d00eb979a7b7d35b890c25562595`.
**Lineage correction, October 6:** this checkpoint contains **199,152 specialist
PPO decisions**, not the 250,000 endpoint as originally stated here. The recorded
checkpoint, weights, experiment outputs and historical hashes are unchanged.
It uses the 48-wide, two-layer combat graph, `commit_decisions_v1`, and the exact
unshaped `combat_win + 0.1 × winning HP fraction` objective with PPO gamma 1.
This was a compatibility choice, not a new comparison selecting the project's
best checkpoint. The student smoke test was not promoted or used for evaluation.

All pilots used Ironclad A0 on local macOS 26.6.2 arm64, Python 3.11.15,
PyTorch 2.13.0, CPU inference with one Torch thread per worker. The planner's seed
was 0, depth ceiling 64, per-action deadline 5 seconds, candidate limit 16.
Evaluation used deterministic root ranking; collection/reanalysis enabled
Gumbel exploration. Configurations were fixed before their runs. Only training
and development partitions were opened; no held-out corpus was accessed or
historical implementation binding rewritten.

Machine-readable summaries, source/checkpoint bindings, report digests and
validation details are retained in
[the evidence extract](combat_search_2026_10_04.json). Full local reports and
public traces remain under the `runs/search-*20261004/` paths recorded there;
private replay audits remain in their separate owner-only directories.

## Combat comparison and latency

Eight controlled starter-deck fights used validation indices 100–107, cycling
through `overgrowth_vantom`, `overgrowth_nibbit`, `underdocks_seapunk_weak` and
`underdocks_sludge_spinner`. Each start was paired across greedy, one-action
simulation/critic baseline and Gumbel search. Both search methods used 64
simulations; one worker kept these latency measurements free from test or
collection contention. The complete 24-fight comparison took **100.48 seconds**.

| Controller | Combat wins | Mean HP on its wins | Searched decisions | Mean / p95 searched-action time |
| --- | ---: | ---: | ---: | ---: |
| Greedy checkpoint | 6/8 | 73.00 | — | — |
| One-action baseline | 6/8 | 73.67 | 89/115 | 0.35 / 0.44 s |
| Gumbel tree | 6/8 | 73.00 | 91/120 | 0.71 / 1.00 s |

All searched decisions completed all 64 simulations. The longest Gumbel action
took **1.044 seconds**; there were no search deadlines, episode cutoffs or
failures. The remaining decisions had one action under the checkpoint's mask.
Both Vantom starts were losses for every controller; the other six fights were
wins. The paired win difference was zero, with the conservative 95% bound
**[−96.0, +96.0] percentage points** for both search methods. This small,
deliberately restricted population establishes neither improvement nor
equivalence. The one-action baseline's HP difference is descriptive only.

For Gumbel, total measured policy time was 64.77 seconds: public projection
31.58 s, inference 22.64 s, fresh-world sampling 4.30 s, rule transitions 3.69 s
and root reconstruction 0.31 s. The remainder is tree/control overhead. There
is no cloning of the actual engine; world construction is measured as sampling.
These measurements favor projection/inference work before a simulator rewrite
or learned dynamics. The five-second play target was met on this tested subset,
not established for every checkpoint or future content extension.

A separate probe replayed the first recorded opening as public input with a
256-simulation budget. It completed all 256 simulations in **3.69 seconds** with
no fallback or deadline. This single position checks the research setting;
it is not a 256-simulation latency distribution or strength comparison.

## Campaign coverage

Four genuine development campaigns (indices 100–103, two starts per Act 1
region) compared the same combat checkpoint and noncombat heuristic under all
three controllers, with four workers. Episode limits were 1,024 decisions and
3,600 seconds. The twelve campaigns completed in **24.44 seconds**, without
operational failures or cutoffs.

Every controller cleared **1/4** campaigns, won 33 combats, lost three combats
and used 23 potions. Each searched controller encountered 563 combat decisions:
112 were forced and **451 fell back on unsupported content; zero were
searched**. Representative blockers were Tremble, Infernal Blade, Hemokinesis,
card provenance, Fishing Rod, Lava Rock and New Leaf. Exact first-failure counts
are in the extract; they are not an exhaustive dependency census.

Consequently this run validates routing, fallback and outcome accounting only.
It does **not measure the benefit of search in campaigns**. The paired Act 1
difference is zero with a 95% bound of [−100, +100] percentage points. Broad
campaign use needs more content reconstruction before a meaningful efficacy
test. Search stays disabled by default.

## Learning and critic checks

An eight-fight training smoke collection used the same controlled encounter
cycle and indices with 16 simulations, Gumbel noise and four workers. It took
**7.52 seconds**, completed 118 decisions (15.69/s), and produced 87 searched
targets (11.57/s) from eight completed fights, with 1,392 simulations. There
were no failures, deadlines or unfinished fights. This is a throughput and
pipeline check, not evidence of training effectiveness or worker scaling.

Two optimizer updates consumed these 87 soft targets and actual completed
returns, publishing a separate student marked `not_evaluated`. Reanalysis then
refreshed the training policy targets with that student; original trajectory and
training-return files remained byte-identical for all eight episodes. Reanalysis
took 15.99 seconds and refreshed 87 searched targets. Cutoff/value-label behavior is
also exercised separately by regression tests. Larger training rounds remain
gated on useful combat search.

The bounded critic audit examined eight public positions from completed greedy
development fights, with four model rollouts per position and depth at most 64.
All 32 rollouts completed; the mean absolute error against the original
completed behavior return was **0.188**. Search and greedy agreed on all eight
audited root choices. This is a small diagnostic, not a calibrated error bound
or evidence that the critic is accurate on untested content.

## Validation and review

The initial full repository run reported **9,110 passed, one skipped**, with
two sandbox loopback-bind failures and the package inventory assertion needing
the new shared CLI module. The package assertion was updated; both loopback
tests then passed with local-socket permission in 0.61 s. After the final
corrections, **144 affected checks passed in 73.87 s**, including search,
training, runner, checkpoint, workers, tracking, combat and installed-command
boundaries. `compileall` and whitespace checks passed.

An independent semantic review found no remaining blocker in the restricted
public-information/RNG model, selector history, cleanup ownership, truncation
labels, reanalysis provenance or tracking identities. Its follow-up reviewed
the Neow extension, final-two scheduling and campaign metrics and passed six
focused checks. This review does not certify unimplemented content or native
live-game parity.

Available timings: full suite 1,768.84 s; final affected suite 73.87 s; benchmark,
collection, audit, distillation and reanalysis durations are bound in the
extract. A complete implementation/review elapsed time was not retained. No
live package/install step or user setup wait was needed.

## Research basis and next gate

- [POMCP](https://proceedings.neurips.cc/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf):
  share decisions by observable history while sampling latent worlds.
- [Gumbel planning](https://openreview.net/pdf?id=bERaNdoegnO) and the authors'
  [sequential-halving reference](https://github.com/google-deepmind/mctx/blob/main/mctx/_src/seq_halving.py):
  small-budget action allocation and completed-value policy improvement. Formal
  guarantees do not transfer automatically to these approximate beliefs/critics.
- [MuZero](https://arxiv.org/abs/1911.08265) and
  [Reanalyse](https://arxiv.org/abs/2104.06294): use refreshed search targets now;
  defer learning transitions while an exact engine is available and measured
  rule execution is a small part of planning cost.

The next useful work is to extend reconstruction through the measured campaign
blockers with conformance tests and obtain informative paired combat starts.
Improve/calibrate the critic where disagreement analysis warrants it before
increasing depth. Require credible combat gains before scaling training and a
positive paired Act 1 result with a 95% interval excluding zero before making
search the default. No such gate passed in this pilot.
