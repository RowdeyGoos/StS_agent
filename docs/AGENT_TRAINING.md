# Agent training guide

Prepared 2026-09-28; current workflow updated 2026-09-30.
**Status: milestones 1–7 implemented and validated.**
**Current training goal: clear Act 1 with Ironclad at A0.** Measure improvement
by paired Act 1 clear rate across Overgrowth and Underdocks. Training all three
acts is deferred until this goal shows useful progress. The next learning focus is
**combat specialization**, with fixed noncombat decisions in hybrid Act 1 checks;
see [campaign-derived combat training](#campaign-derived-combat-training) and
[Act 1 training and configurable act rewards](#act-1-training-and-configurable-act-rewards).
The user authorized milestones 1–7 and requested a summary of key
implementation details and choices after each milestone. A bounded CPU imitation
warm-up and hybrid development evaluation are included in milestone 3. Milestone 4
adds bounded PPO and controlled learning checks, with continued hybrid evaluation.
Milestone 5 adds a frozen paired benchmark and a finite combat curriculum.
Milestone 6 extends the shared learner to full runs with a distinct objective,
broader demonstrations and paired genuine campaign evaluation. Milestone 7
checks the installed commands, dependency boundaries and complete delivery workflow.

This document owns training usage, implementation choices and measured results. The [target](TARGET.md)
owns the full-game objective, the [public contract](AGENT_CONTRACT.md) owns actor
information, and the [execution guide](AGENT_EXECUTION.md) owns existing recordings
and workers. The retired training pipelines are not implementation dependencies.

## Campaign-derived combat training

Freeze actual Act 1 combat starts before training. The corpus builder runs
Ironclad A0 campaigns through both Overgrowth and Underdocks, using a fixed public
heuristic or an explicitly supplied full-run checkpoint as the collector. Every
reached ordinary fight, elite and boss is captured before the collector's first
combat action. This preserves the campaign's real deck, upgrades, HP, relics,
potions, draw order and RNG state, including fights from campaigns that later die.
It does not equip invented late-game decks or retry losing source campaigns.

```bash
sts-agent-train build-combat-corpus --output-dir runs/combat-corpus \
  --checkpoint runs/act1-increased-500k-8workers-20260930/chunk-15/final.sts-model \
  --train-campaigns 32 --validation-campaigns 16 --test-campaigns 16 \
  --route-policy mixed_elites --capture-turns 8
```

Counts are **per region** (128 campaigns in this example). The default source
limit is 1,024 decisions / 120 seconds per campaign, stopping at the Act 1
completion boundary. Omit `--checkpoint` to use the heuristic. The default
private seed offset is 1,000,000; choose a fresh `--start-index` when building a
new experimental population. Splits are assigned to entire source campaigns
before play: fights from one campaign can never cross train/validation/test.

The v2 corpus supports `--route-policy mixed_elites`: alternating campaigns in
each region/split use the collector's original route or a route maximizing the
number of reachable elites. The route chooser reads only legal choices and the
public map graph; combat, rewards and other choices still use the frozen
collector. Losing sources remain in the corpus, without retries or HP/inventory
assistance. Defaults remain `collector` routing and one opening per fight.

`--capture-turns 8` also freezes the first ordinary player decision in turns 2–8
when reached, with a maximum of eight starts per combat (allowed range 1–12).
It waits for pending enemy/card selections to finish before capturing a later
turn. These states preserve real hand/deck order, enemy powers, HP, potions and
RNG. Their purpose is direct practice of blocking, potion timing and changing
enemy mechanics such as Vantom's Slippery stacks. They are collector-conditioned
states, not new independent fights or expert action labels. Openings and all
continuations share both a combat ID and their campaign's split.

The public `corpus.json` lists opaque case and campaign IDs, encounter/floor,
inventory and initial-public-state digests, actual HP/deck ranges, coverage by
region and fight type, and missing encounter/region/type combinations. It also
reports opening/continuation counts, missing elites/bosses, potion availability
by type, HP bands, displayed attack pressure and visible enemy powers. Attack
pressure uses displayed damage × hits minus current block, not a forecast of
all end-turn effects. A relic-choice context that hides combat reports this
information as unavailable. Inspect
these gaps before setting a training budget. Collector survival and routing bias
remain: later fights only contain inventories that this collector reached.
The private sibling directory contains owner-only seed mappings and exact engine
snapshots. Keep both directories together; the actor only sees public decisions.
Restoration checks snapshot bytes, source campaign seed, and public initial state;
each episode gets a fresh engine and fresh adapter history.
Snapshot JSON preserves engine map insertion order, including visible potion
powers. The builder derives the initial public digest from the exact bytes it
publishes; generic sorted-key report serialization must not be used for engine
snapshots. A Liquid Bronze + Regen regression covers this later-turn boundary.

The builder also writes `combat-training.json` and `combat-ppo.json`. Their
default task reward is **+1 for combat victory plus 0.1 × remaining HP fraction
on victory**; other components are zero. HP is a smaller shaping term than victory.
Weights remain configurable through the existing combat reward schema. PPO's
source binds the exact corpus identity. Its `encounters` configuration now names
the available room-kind buckets (`combat`, `elite`, `boss`): the deterministic
episode schedule gives each kind equal frequency. Within each kind, a seeded
local RNG chooses an encounter uniformly, then a source fight uniformly. It
chooses opening versus continuation with equal probability when both exist,
then a later turn uniformly. Long fights therefore do not gain sampling weight
simply because they produced more snapshots. A missing kind is omitted from the
generated config and reported in coverage; this is never an all-encounter claim.
Neither training collection nor vocabulary fitting loads held-out combat starts.
Missing encounters cannot be silently supplied from another source.

Use the existing imitation learner and graph actor-critic (default hidden size
48, two message layers), followed by combat PPO:

```bash
sts-agent-train collect --combat-corpus runs/combat-corpus/corpus.json \
  --split train --output-dir runs/combat-demos-train --max-decisions 512 --time-limit 120
sts-agent-train collect --combat-corpus runs/combat-corpus/corpus.json \
  --split validation --output-dir runs/combat-demos-validation --max-decisions 512 --time-limit 120
sts-agent-train imitate --train-dir runs/combat-demos-train \
  --validation-dir runs/combat-demos-validation --output-dir runs/combat-imitation \
  --action-policy commit_decisions_v1 --updates 128
sts-agent-train ppo --checkpoint runs/combat-imitation/final.sts-model \
  --config runs/combat-corpus/combat-ppo.json --combat-corpus runs/combat-corpus/corpus.json \
  --output-dir runs/combat-ppo --decisions 20000 --workers 8
```

Demonstrations use each requested train/validation fight once; `--split test`
is rejected. PPO retains the existing commit-selection policy, native selection
order, 1–8 persistent collectors, and checkpoint/resume workflow. The generated
rollout is 4,096 total decisions, with 512 decisions / 120 seconds per fight and
two optimization epochs. Resume with the same corpus, experiment, implementation
and worker allocation, using the matching `.resume.pt` file. A different corpus
or factory is rejected at learner creation and collection. Existing full-run
checkpoints can be **benchmark actors** below; this does not reinterpret their
run-value critic as a combat critic or enable cross-objective exact resume.

```bash
sts-agent-evaluate --combat-corpus runs/combat-corpus/corpus.json \
  --candidate warmup=runs/combat-imitation/final.sts-model \
  --candidate combat_20k=runs/combat-ppo/final.sts-model \
  --split validation --output-dir runs/combat-evaluation \
  --max-decisions 512 --time-limit 120 --workers 8
```

Add named 250k/500k full-run checkpoints to compare their combat choices directly.
Every policy, including heuristic and random-legal baselines, receives the **same
frozen start**. The benchmark writes a plan before running games and then
`combat-benchmark.json`, with overall and per-encounter/region/fight-type wins,
losses, cutoffs, HP, potion use, turns and paired win differences. All planned
cases remain in denominators after failures or cancellation. Confidence bounds
group fights by source campaign; correlated fights are not independent trials.
These results measure the frozen combat population, not Act 1 clear probability.
HP on wins is conditional on winning; net HP changes include cleanup healing.

Corpus evaluation defaults to `--combat-starts opening`, measuring complete
fights only. Use `--combat-starts continuation` for a separate tactical diagnostic,
or `all` for an explicitly mixed population. Reports group outcomes by encounter,
fight type, starting HP, attack pressure and potion availability; these groupings
describe outcomes, not a proof that an individual block/potion decision was
optimal. The held-out test lock also binds the chosen start population.
Do not compare continuation win rates to full-fight win rates. Expanding the
corpus requires a new corpus-bound training run; it is not an exact optimizer
resume from a different corpus, and it does not itself update a model.

Keep `--split test` for the final, preselected comparison. Its first use locks the
checkpoint identities and limits before loading any test snapshots. Different
test candidates/limits and subsequent validation benchmarks on that corpus are
rejected. Use a new population for another held-out claim after further tuning.
Test starts are never used as imitation demonstrations or PPO samples.

Completed public combat trajectories work with `sts-agent-analyze build`; combat
task rewards remain in their separate sidecars. The new benchmark's grouped
metrics are in its JSON report, rather than the viewer's full-run learning charts.
For Act 1 integration, reuse `sts-agent-evaluate --act1 --checkpoint FULL_RUN_MODEL
--combat-checkpoint COMBAT_MODEL ... --workers 8`: the hybrid uses the combat
model inside fights and the unchanged heuristic for other decisions. Keep that
controller and campaign cases fixed when comparing combat checkpoints.

### Expanded combat population (2026-09-30)

The current corpus is `runs/act1-combat-expanded-verified-20260930/corpus.json`.
It uses the frozen 500k Act 1 collector, mixed elite routes and up to eight
reached turns per fight. All **42 regional Act 1 encounters**, including all six
elites and six bosses, appear in every split. Native event fights reached on the
route are retained too. The 128 unassisted campaigns yielded:

| Split | Source campaigns | Fights | Opening + later-turn starts | Elite fights | Boss fights | Starts with potions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 64 | 502 | 1,873 | 53 | 35 | 290 |
| Validation | 32 | 250 | 920 | 38 | 12 | 116 |
| Test | 32 | 267 | 997 | 34 | 16 | 128 |

This expands training from 150 fights (two elites, 13 bosses) to 502 fights and
1,873 practice starts. Each room kind receives one third of the default training
schedule. Collection took **9m 28s**. Test gameplay evaluation remains unopened.
The expansion itself did not train a policy. The subsequent
[fresh 250k experiment](#fresh-combat-policy-250k-decisions-2026-09-30) binds this
corpus and fits its vocabulary on expanded training observations.

All **2,793 train/validation starts** pass two independent exact restores, their
public digest check, one direct legal action, and isolation from the untouched
second instance. They contain 384 states with a legal potion-use action, 1,922
with a playable block card under unblocked/lethal displayed attack pressure,
and 455 with a playable block card but no displayed attack. Vantom contributes
33 states with Slippery active and 33 with it depleted, covering all stack counts
0–8 and all four move phases. These are coverage counts, not optimal-action
labels. Restoration verification took 29.7 seconds; **99 focused checks** passed
in 2m 43s, including parallel PPO/resume and evaluation. Independent semantic
review found no remaining blockers.

The unchanged 500k Act 1 actor wins **224/250** full-fight validation starts:
190/200 ordinary fights, 30/38 elites and 4/12 bosses (including 1/4 Vantom).
The heuristic wins 212/250 and random legal wins 145/250. All 750 planned games
finish without failures or cutoffs in 58.5 seconds with eight workers. These are
small, campaign-conditioned boss samples; they motivate the training focus,
not a general boss mastery claim or evidence of a newly improved model.
`runs/combat-inspection-expanded-20260930` exports all 750 episodes / 10,512
decisions, with public trajectories grouped by policy. Its canonical run cutoff
labels still differ from combat victory; the combat benchmark JSON owns the
fight-win counts. Full configuration, coverage, hashes and checks are recorded in
[expansion evidence](evidence/combat_corpus_expansion_2026_09_30.json).

The first collection, `runs/act1-combat-expanded-20260930`, was rejected by
restoration verification: sorted JSON keys reordered visible potion powers in
some continuations. It was retained for diagnosis and replaced by a fresh
collection under the fixed implementation, with no old hash/evidence repinning.

### Fresh combat policy: 250k decisions (2026-09-30)

`runs/combat-fresh-250k-20260930` trains one new actor and critic for exactly
**250,000 PPO decisions with eight workers**. All weights and the optimizer start
fresh; no Act 1 or imitation weights are transferred. The existing 48-wide,
two-layer graph architecture has 80,738 parameters with this vocabulary. A
training-only heuristic pass over all 1,873 starts produces 16,920 public
observations for fitting 627 vocabulary names; those actions are not imitation
targets, and no validation/test observations enter fitting.

The objective is the corpus preset: **+1 combat win and +0.1 × HP fraction on
victory**, with other components zero and `commit_decisions_v1` unchanged. The
run retains 4,096-decision rollouts, two optimization epochs, learning rate
0.0003 and the balanced encounter/fight/turn sampler. Its 15,399 episode attempts
use 1,729 distinct training starts: 5,129 ordinary fights, 5,091 elites and 5,179
bosses; 7,685 openings and 7,714 continuations. Potions are available in 4,616
starts. All 250,000 decisions receive updates, with no skipped updates or failed
game episodes. There are 485 training decision-budget cutoffs, retained with
the existing bootstrap semantics.

The predeclared checkpoints are `chunk-03/final.sts-model` (50k),
`chunk-06/final.sts-model` (100k), `chunk-09/final.sts-model` (150k),
`chunk-12/final.sts-model` (200k) and `chunk-15/final.sts-model` (250k).
Matching exact optimizer/RNG resume files live under the owner-only sibling
`runs/combat-fresh-250k-20260930-private`. Every closed update is retained too.

One local orchestration error interrupted worker startup after **66,384** trained
decisions: a helper named `inspect.py` shadowed Python's standard library.
The helper was renamed, the stalled process was stopped and cleanup verified,
and training resumed exactly from `chunk-04/final.sts-model` into
`chunk-05-resumed`. The failed `chunk-05` attempt had no games or updates and is
preserved. Production sources, corpus bindings, rewards and the original protocol
were unchanged. All 15 completed chunk boundaries pass exact restore checks.

After training, all checkpoints receive the same **250 validation openings**:

| Policy | All fights / 250 | Ordinary / 200 | Elites / 38 | Bosses / 12 | Vantom / 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Untrained fresh actor | 208 | 188 | 19 | 1 | 0 |
| Fresh combat 50k | 218 | 192 | 23 | 3 | 2 |
| Fresh combat 100k | 211 | 185 | 24 | 2 | 1 |
| Fresh combat 150k | 211 | 185 | 24 | 2 | 1 |
| Fresh combat 200k | 211 | 185 | 24 | 2 | 1 |
| Fresh combat 250k | 214 | 186 | 25 | 3 | 2 |
| Existing Act 1 500k | 224 | 190 | 30 | 4 | 1 |
| Heuristic | 212 | 188 | 23 | 1 | 0 |
| Random legal | 145 | 139 | 6 | 0 | 0 |

The final model wins **85.6%**, versus 89.6% for the existing Act 1 actor, 84.8%
for the heuristic and 83.2% for its untrained initialization. Against the Act 1
actor it gains three cases and loses thirteen; no specialized-model improvement
over that reference is established. The 50k checkpoint leads this development
curve at 87.2%, but no checkpoint is automatically promoted. The final model's
mean HP fraction on wins is 64.74%, versus 61.76% for the reference; these are
different sets of won fights. Both make 115 potion-use actions, so the aggregate
count does not establish better potion timing. Vantom's 2/4 versus 1/4 is a small
descriptive sample, not evidence of general boss mastery.

PPO takes **34m 28.6s**: 23m 12.3s collecting, 11m 3.2s updating, with the
remaining time in checkpointing/orchestration. Vocabulary fitting takes 112.2s
after its separate observation collection. The eight-worker validation takes
**3m 21.1s** for all 2,250 games, with no failures or cutoffs. Final verification
takes 2.4s; exporting 750 final/reference/heuristic games and 10,150 decisions
takes 10.4s. Setup and the interrupted worker-start attempt are outside the PPO
timing. No held-out test evaluation was opened, and this is one learner seed.

The inspector data is `runs/combat-fresh-250k-20260930-inspection`. Its run outcome
labels remain canonical campaign outcomes; the combat benchmark report owns the
fight-win counts. The [experiment evidence](evidence/combat_fresh_250k_2026_09_30.json)
records the configuration, train-only vocabulary, sampling counts, complete curve,
checkpoint identities, recovery, timings and operational checks. The subsequent
[500k extension](#fresh-combat-policy-500k-decisions-2026-09-30) continues this exact
learner and retains the original artifacts.

### Fresh combat policy: 500k decisions (2026-09-30)

`runs/combat-fresh-500k-20260930` resumes the fresh combat learner at 250k and
trains **250,000 additional decisions, reaching 500,000 total**. The actor, critic,
optimizer, RNG and episode cursor all continue exactly. Eight workers, the
expanded training corpus, balanced sampler, frozen vocabulary, architecture,
`commit_decisions_v1` and rewards (+1 win, +0.1 × HP fraction on victory) remain
unchanged. No imitation or vocabulary refitting occurs during the extension.

The retained checkpoints are `chunk-03/final.sts-model` (300k),
`chunk-06/final.sts-model` (350k), `chunk-09/final.sts-model` (400k),
`chunk-12/final.sts-model` (450k) and `chunk-15/final.sts-model` (500k).
Exact resume files live in the matching directories under the owner-only sibling
`runs/combat-fresh-500k-20260930-private`. Every closed update is retained too.

All additional decisions receive updates, with no failed episodes or skipped
updates. The 15,564 episode attempts comprise 10,368 wins, 4,707 defeats and
489 decision-budget cutoffs using the existing bootstrap semantics. They use
1,767 distinct training starts: 5,179 ordinary, 5,151 elite and 5,234 boss starts;
7,795 openings and 7,769 continuations. Potions are available in 4,670 starts.

All five new milestones, the 250k parent and the fixed reference policies receive
the same **250 validation openings**:

| Policy | All fights / 250 | Ordinary / 200 | Elites / 38 | Bosses / 12 | Vantom / 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fresh combat 250k parent | 214 | 186 | 25 | 3 | 2 |
| Fresh combat 300k | 217 | 189 | 25 | 3 | 2 |
| Fresh combat 350k | 217 | 191 | 22 | 4 | 2 |
| Fresh combat 400k | 212 | 190 | 20 | 2 | 0 |
| Fresh combat 450k | 218 | 189 | 26 | 3 | 0 |
| Fresh combat 500k | 213 | 187 | 23 | 3 | 1 |
| Existing Act 1 500k | 224 | 190 | 30 | 4 | 1 |
| Heuristic | 212 | 188 | 23 | 1 | 0 |
| Random legal | 145 | 139 | 6 | 0 | 0 |

The final model wins **85.2%**, versus 85.6% for its parent and 89.6% for the
Act 1 reference. Relative to its parent it gains seven fights and loses eight;
relative to the Act 1 reference it gains two and loses thirteen. More decisions
have not established an overall improvement. The 450k checkpoint leads this
extension at 87.2%, tying the original 50k checkpoint; no checkpoint is
automatically promoted. Final mean HP fraction on wins is 64.10%, versus 64.74%
at 250k, conditional on different sets of won fights. Potion-use actions fall
from 115 to 108; aggregate counts do not establish whether timing improved.
The four Vantom starts remain a small descriptive sample.

Additional PPO takes **34m 01.9s**: 22m 54.8s collecting and 10m 54.4s updating,
with the remainder in checkpointing/orchestration. Eight-worker validation takes
**3m 14.6s** for 2,250 games, with no failures or cutoffs. All 15 completed chunk
boundaries restore exactly. All 1,000 repeated parent/Act 1/heuristic/random games
reproduce their earlier gameplay outcomes, HP, steps, potion use and task returns.
Final verification takes 1.7s; exporting 1,000 final/parent/reference/heuristic games
and 13,897 decisions takes 13.6s. Test evaluation remains unopened, and no hybrid
full Act 1 evaluation or learner-seed replication is part of this extension.

The inspector data is `runs/combat-fresh-500k-20260930-inspection`. Its canonical
campaign cutoff labels still differ from combat victory; the combat benchmark
JSON owns fight-win counts. The [extension evidence](evidence/combat_fresh_500k_2026_09_30.json)
records the parent bindings, exact continuation, full 0–500k learning curve,
sampling, checkpoint hashes, timings and checks. The following diagnostic examines
the plateau before another budget increase.

### Combat learning plateau diagnostic (2026-10-01)

`runs/combat-diagnostic-20261001` compares the unchanged saved actors on all
502 training openings against the bound, previously evaluated 250 validation
openings. Six validation starts under two models reproduce all material results
exactly before the larger comparison. The engine, public projection, model
architecture, vocabulary, rewards and existing training artifacts remain unchanged.
This is development evidence; no held-out test was opened.

| Policy | Greedy training wins / 502 | Greedy validation wins / 250 |
| --- | ---: | ---: |
| Untrained initialization | 443 | 208 |
| Combat 50k | 457 | 218 |
| Combat 250k | 461 | 214 |
| Combat 500k | 460 | 213 |
| Act 1 500k reference | 453 | 224 |
| Heuristic | 443 | 212 |

The training/validation gap is largely present at initialization. Giving ordinary,
elite and boss openings equal weight yields 61.6%/50.8% before training and
72.4%/59.7% at 500k. These remain different, collector-conditioned populations;
their gap alone does not establish overfitting as the plateau's main cause.

A separate panel freezes **36 openings per split: 12 ordinary, 12 elite and
12 boss fights**. Each checkpoint uses the same two explicit action-RNG seeds per
case. Sampling uses the production PPO distribution and candidate-ref mapping;
it does not consume the engine RNG. This panel deliberately weights difficult
fights more heavily than the full opening benchmark.

| Policy | Sampled train wins / 72 | Sampled validation wins / 72 | Greedy validation wins / 36 |
| --- | ---: | ---: | ---: |
| Untrained initialization | 22 | 17 | 17 |
| Combat 50k | 36 | 27 | 20 |
| Combat 500k | 47 | 43 | 19 |

The observed sampled-policy improvement is substantial on this small panel,
despite the much flatter greedy curve. Greedy-only reporting misses part of the
learning progress. Two repetitions are not independent source campaigns and do
not establish that sampled deployment improves the entire validation population.
The production combat benchmark remains greedy; both modes are available in this
bound diagnostic harness.

The learnability test starts from the original untrained actor/critic with a fresh
optimizer, RNG and cursor. It uses **50,000 decisions and eight workers**, with
10k/25k/50k checkpoints, on 32 training states with recorded heuristic victories:
eight immediate kills, ten states with block available under incoming damage,
ten with potions used by the winning witness, and four Vantom turns. These are
29 fights from 21 source campaigns; the four Vantom turns share one fight.
Worker schedules cycle deterministically, with unequal episode exposure under
fixed decision quotas. No validation case can enter the subset factory.

Greedy wins at 0/10k/25k/50k are **29/29/30/30 out of 32**. The predeclared 31/32
target is not met. Sampled wins rise from **38/64 to 58/64**; Vantom rises from
3/8 to 8/8 on those repeated training starts. The final greedy failures are a
Waterfall Giant and Ruby Raiders start. This is memorization evidence, not new
generalization evidence or proof that representation capacity is the bottleneck.

The chosen set has limited tactical headroom: the untrained greedy actor already
wins every immediate-kill, block-pressure and Vantom case. Removing potion use
from the heuristic still wins nine of the ten potion cases. Availability and a
winning demonstration therefore do not establish that the intended tactic is
necessary. The next useful change is to track both greedy and sampled checkpoint
evaluation and build harder, verified tactical cases that distinguish potion
timing, blocking and boss sequencing. A larger model or another long continuation
is not justified by this diagnostic alone.

All 50,000 decisions receive updates, with no failed training episodes, skipped
updates or KL early stops; all four chunk boundaries restore exactly. PPO takes
**7m 6.5s** (4m 56.0s collection, 2m 7.0s updates). The initial 3,112-game diagnostic
takes 5m 12.6s, and the final 160-game evaluation takes 15.8s; all complete without
failures or decision cutoffs. Verification covers 32 independent restore pairs,
768 legal/repeatable sampled selections, unchanged global Torch RNG, and rejection
of validation, unlisted and incorrectly bound cases. The independent semantic
review found no remaining blockers after adding configuration binding and a
mandatory verification gate.

The inspector dataset, `runs/combat-diagnostic-20261001-inspection`, contains 128
unchanged public traces and 1,370 decisions: untrained, existing combat 500k,
diagnostic 50k and winning heuristic on each start. Canonical campaign cutoffs
remain distinct from combat wins. The [diagnostic evidence](evidence/combat_plateau_diagnostic_2026_10_01.json)
binds the protocols, results, checkpoints, verification and inspection export.
The original 500k model remains the existing combat candidate; the tiny-set model
is retained only for diagnosis.

### Initial combat corpus pilot (2026-09-30)

Initial delivery check (2026-09-30):
`runs/act1-combat-corpus-20260930/corpus.json` contains **297 fights from 32
campaigns**, split into 150 train / 74 validation / 73 test starts. The fixed
collector is the existing 500k Act 1 model. Training covers 38 encounter IDs,
with 135 ordinary fights, two elites and 13 bosses; its real decks contain 10–21
cards and starting HP spans 8–80. Validation lacks an Underdocks elite, so this
is a pilot population requiring broader elite coverage before a long experiment.

**The initial combat comparison is invalid for policy-strength claims.** The
action-mapping correction below supersedes its interpretation; its original
artifacts and measurements are retained. The eight-worker comparison completed all **296 validation games in
35.29 seconds**, without failures or cutoffs. Both existing 250k and 500k actors
won 67/74 fights, compared with 66/74 for the heuristic and 46/74 for random-legal.
Both labelled learned actors won 64/65 ordinary fights and 1/7 bosses, but those
games did not always execute the chosen action. The 500k actor's mean HP fraction on
wins was 69.0%, versus 65.4% at 250k. The held-out benchmark remains unopened.

All 154 affected checks pass after correcting one existing CLI diagnostic
expectation; independent semantic review closed three concrete findings. Installed
commands also completed eight imitation updates with the unchanged 48-wide,
two-layer model, 256 PPO decisions plus an exact 256-decision continuation using
eight workers, and six paired Act 1 integration games including the combat hybrid.
The two hybrid games ended in defeat; these tiny training runs prove integration,
not improved playing strength. Corpus collection took 176.97 seconds, imitation
62.48 seconds, the two PPO chunks 7.39/7.52 seconds, and hybrid comparison 21.66
seconds. Some work ran concurrently. The [delivery evidence](evidence/combat_specialization_pilot_2026_09_30.json)
retains artifacts, hashes, coverage gaps, commands and review/validation timings.

### Combat evaluation action mapping correction (2026-09-30)

Combat evaluation and demonstration collection previously passed a candidate's
position in `env.public_state.candidates` to Gym. Gym expects its encoded action
slot, which sorts by public-reference traversal and can differ after history
references a card. A policy could choose Perfected Strike while Strike actually
played, and the recorder would label that transition with the intended card.
Card-selection actions were affected too. The shared evaluator now resolves
the exact current candidate through `env.action_index(candidate)`; tensor layout,
native commands and card rules are unchanged.

The reported episode `3fd80e938a23438ea6ba8663906bcb2d` reproduced all 37 original
transitions through the faulty path, with ten mismatched actions. At index 29,
the intended Perfected Strike occupied public position 4 but encoded slot 0.
Correct dispatch spent two energy, discarded Perfected Strike and reduced
Vantom from 76 to 56 HP; the historical record spent one energy, discarded Strike
and reduced HP to 70. This is a controlled diagnosis, not a new benchmark.

Previous combat baseline/benchmark reports and combat demonstration transitions
from this evaluator require regeneration before policy comparison or value
training. This includes the pilot's matched comparison and imitation warm-up;
its 512-decision combat model is only an integration smoke artifact. Preserve
original records and hashes. Rebuild the source-bound corpus under the corrected
implementation before new collection; do not repin its old source identity.
PPO collection already dispatches encoded slots correctly, and campaign corpus
collection, full-run demonstrations and Act 1/full-run evaluation dispatch
candidate references directly. Their action dispatch is unaffected by this bug.
Replay regressions now compare recorded successors against independent direct
adapter execution, including the differing card order after a redraw.

Regeneration is complete under the corrected implementation. Use
`runs/act1-combat-corpus-corrected-20260930/corpus.json`: all 297 initial public
states, inventories and native snapshots exactly match their original cases.
The new train/validation demonstration directories contain 150/74 episodes and
2,039/999 decisions. The eight-worker comparison in
`runs/act1-combat-matched-corrected-20260930/combat-benchmark.json` completed all
296 games without failures or cutoffs in 26.37 seconds. Both existing Act 1
actors won 67/74, the heuristic 66/74 and random-legal 43/74. Each learned actor
won 64/65 ordinary fights, 2/2 elites and 1/7 bosses. Random-legal has fresh
case-derived policy RNG because the rebuilt cases have new opaque IDs; game
starts and game RNG are unchanged. These are development combat results on
eight source campaigns, not Act 1 clear rates or evidence of model improvement.

The replacement smoke in `runs/act1-combat-smoke-corrected-20260930/` starts from
clean demonstrations, repeats eight imitation updates and 256 + 256 PPO decisions
with eight workers, and verifies exact checkpoint resume. It is still only a
512-decision integration model. Corpus generation took 145.06 seconds, imitation
55.72 seconds and PPO 6.20/6.27 seconds; overlapping phases are not summed into a
throughput claim. No held-out benchmark was opened.

All 558 regenerated evaluation, demonstration and PPO episodes were independently
replayed by restoring their starts and dispatching recorded references directly
through the adapter, comparing exact execution reports and public successors:
**7,822 actions, zero mismatches**, including card selections. The rebuilt
`runs/combat-inspection-corrected-20260930/` viewer contains those unchanged public
recordings and supports comparison with the clean smoke and existing 250k/500k
checkpoints. The old Vantom episode maps to `130b89feb58245778da56b0063679e1e`;
its corrected sequence has 29 decisions. Combat victories still appear as
canonical external stops in this viewer; use the combat benchmark for task wins.
The [regeneration evidence](evidence/combat_specialization_pilot_2026_09_30.json)
retains new artifact bindings and correspondence separately from the invalid
original comparison, whose files and hashes are preserved.

## Decision analysis tools

`sts-agent-analyze` builds a local report from existing **completed public
recordings**. It does not run the game or change checkpoints. The browser viewer
provides:

- An overview filtered by split, evidence kind and policy, with outcome counts,
  last observed floors, action categories and links into individual runs.
- A floor timeline and decision inspector for combat, card selections/rewards,
  route, shop, rest, event and other public decisions. The inspector retains the
  full public graph, available actions, actual choice and observed successor.
- A map graph with recorded room connections, visited/current rooms, legal next
  rooms and the recorded route choice. Click a room for its public details;
  unknown rooms remain unknown, and map rows are distinct from HUD floor counts.
- Selection-toggle and reward-navigation review signals after at least eight
  consecutive actions including reversals in the same floor/context. These link
  to the exact span. Ending a turn while a card is playable is informational,
  not proof of a bad decision. These exploratory signals are separate from the
  pilot's predeclared last-32-action cutoff metric.
- Full-run PPO collection curves and per-action reward components, recorded
  chosen-action probability, critic value, next value, advantage and return
  target. Combat-only PPO task sidecars are not currently joined; their public
  trajectories can still be inspected without inventing combat outcomes.
- Up to four explicitly supplied checkpoints compared on the **same recorded
  public state**. Native legality and the checkpoint's policy mask remain
  distinct. A forced confirmation is labelled as the only policy-allowed action.

Get the reported experiment results immediately, without building the viewer:

```bash
sts-agent-analyze summary --input runs/act1-50k-8workers-20260929
```

`summary` emits JSON from the compact PPO/evaluation reports. It checks PPO
configuration identities and pinned evaluation plans, retains failed/interrupted/
unattempted cases in the reported denominators, and keeps each source's status,
objective, checkpoint identities and results separate. Consecutive PPO chunks are
not pooled as independent learners. Its validation scope is explicitly
`report_metadata_only`: it does **not** read canonical trajectories, rollout
sidecars or checkpoint files, verify paired starting states, or recompute rewards.
Use these reported metrics for quick feedback; use `build` for independent
recording validation and the decision viewer.

Build once with parallel episode exporters, then serve the report locally:

```bash
sts-agent-analyze build \
  --input runs/act1-pilot-20260929 \
  --output-dir runs/act1-analysis-20260929 --goal act1 --workers 8

sts-agent-analyze serve runs/act1-analysis-20260929 \
  --checkpoint initializer=runs/training-readiness-20260929/filtered-initializer.sts-model \
  --checkpoint learner-2=runs/act1-pilot-20260929/learners/learner-2/final.sts-model
```

Open `http://127.0.0.1:8765`; stop the viewer with Ctrl-C. `--port` selects another
local port. The viewer uses bundled assets without online fonts, scripts or
services. It listens only on loopback, has no mutation endpoints, and serves only
its fixed assets and indexed analysis data. It does not serve the repository.

Repeat `--input` to include more public roots. Discovery skips hidden/private/audit
directories, symlinks and partial files. It reads canonical trajectories and
recognized public evaluation/PPO reports and plans; report strings cannot direct
it to arbitrary files. Include a report's full public directory so its pinned
plan, rollouts and completed episodes are present. Failed/unattempted rows stay
visible in provenance; descriptive table rates use completed recordings and are
not a replacement for the planned-population evaluation metrics. Distinct policy
identities, splits, evidence, source builds/rules and training objectives stay in
separate comparison groups. Paired cases require at least two distinct policy
identities with identical public initial state and source identities.

The builder validates each complete canonical artifact, including its digest,
before export. Full-run PPO joins verify the trajectory identity, episode step,
chosen candidate, legality/policy masks, behavior fingerprint and task boundary;
reward components are recomputed from the public owner measurements. Recorded
learner diagnostics are labelled as recorded, not independently reconstructed.
Comparison probabilities are recomputed from an explicitly loaded inference
bundle. Its identity and objective are displayed; different reward objectives
make critic values incomparable. Neither probabilities nor the critic explain
the model's reasoning or estimate calibrated correctness/Act 1 clear probability.

Act 1-labelled success requires an unfinished Act 1 start and a final public
Act 1 completion boundary with canonical `truncated/external_stop`. Full-campaign
victory remains distinct. Canonical terminal outcomes do not contain terminal HP;
the inspector displays it as unavailable instead of inventing a zero or reusing
the previous HUD. Net HP changes include healing and are not damage totals.

Exports use compressed chunks of 16 decisions, loaded on demand with two chunks
cached. The output directory is new and never overwrites an existing report;
failed builds have no completed `report.json`. `build --workers N` accepts 1–8
workers (default 1). These workers independently validate and export episodes;
they do not run training or inference. Episode identities are reserved before
writing, report order is stable, and paired-start checks run in the parent.
Worker errors stop the export without retries; Ctrl-C stops and cleans up workers
and exits with status 130. Start again with a new output directory after failure
or interruption. Compressed decision contents are the same as serial export.
The CLI reports full elapsed time and the report includes metadata preparation,
episode wall time and summed per-episode phase timings. Summed worker times can
exceed elapsed wall time when workers run in parallel.

The report can be copied and
inspected without its original trajectory files. Core export/inspection and the
viewer use the standard library; checkpoint comparison requires `sts-agent[train]`.

For scripts or a bug report, emit one decision (CLI step indexes are zero-based;
the browser shows one-based step numbers):

```bash
sts-agent-analyze inspect runs/act1-analysis-20260929 \
  --episode b2f9a87449a5498fa3ba1562a4cdf319 --step 1000
```

Add `--checkpoint LABEL=PATH` to emit same-state comparison JSON instead. Browser
links preserve the run and zero-based decision index in their URL fragment.
This is recording playback and inference, not counterfactual simulation. Existing
frozen pilot reports/hashes are preserved. Historical inference bundles remain
loadable; exact learner resume still requires its original implementation identity.

Delivery check (2026-09-29): the pilot export contains 383 trajectories / 44,027
decisions and verifies 16 paired evaluation starts. Export took 394.70 seconds
and produced approximately 279 MB of compressed data/assets. Both known floor-1
selector loops are linked from steps 7–1024 in the browser. The affected agent
integration suite passed 777 tests in 405.65 seconds; subsequent focused checks
cover the final plan-goal guard, observed combat deltas and forced policy
confirmation display. Independent semantic review closed its policy attribution,
pairing and Act 1 horizon findings (367 seconds across review and corrections).
Browser checks exercised overview, loop navigation, same-state inference and
training charts. Export and validation ran concurrently with implementation;
implementation time was not separately measured.

Parallel export benchmark (2026-09-29): on the existing 50k experiment's 541
episodes / 56,844 decisions, the installed `summary` command returned in
**0.128 seconds**, including startup. Full validation/export with eight workers
took **62.98 seconds**, compared with the previously measured 472.88-second
serial export of the same recordings (about **7.5× faster**). This comparison
reuses the historical serial timing; cache state and host load were not controlled.
All 3,801 compressed decision chunks (340,140,044 bytes) match the original
export byte for byte, as do every episode row and all 16 paired-start checks.
Sorting episode IDs before reducing collection returns makes aggregation order
stable; the largest difference from the old unsorted mean was 1.67e-16.

Summed worker phase time was about 57.2% canonical loading/validation and 41.8%
encoding/compression/writing; these are shares of worker time, not elapsed time.
The 39 focused analysis tests passed in 11.21 seconds, including the loopback
viewer check, and seven package checks passed in 5.63 seconds. Changed modules
compiled successfully. Independent semantic review took 166 seconds and found
no blockers; large-transfer, abrupt-exit and Ctrl-C probes left no worker or
transfer-thread leaks. Whole-export parity checking took 0.78 seconds.
The [benchmark evidence](evidence/analysis_export_optimization_2026_09_29.json)
retains source identities, timings, parity checks and artifact hashes. Benchmark
outputs are under `runs/analysis-export-optimization-20260929/`; earlier
experiment artifacts and the currently served viewer remain intact.

## Intended result

Deliver a trainable policy over the existing legal candidates, configurable
training objectives, reproducible evaluation, and checkpoints that the current
agent execution path can load. Start with isolated Ironclad A0 fights. As soon as
the first usable combat checkpoint exists, evaluate it in full campaigns with the
existing heuristic handling other decisions. Continue those evaluations alongside
combat training, then extend learning to every run decision once the pipeline is
reliable and combat learning shows progress.

The first observable acceptance case is a seeded, ordinary-HP Ironclad encounter:
initialize its deck and starter relic through existing game APIs, observe public
state, choose legal candidates including any nested combat selections, finish the
fight, assign the configured combat reward exactly once, and reset independently.
A small learned checkpoint must reload and play that same task through the public
adapter. This proves integration; separate evaluation establishes playing strength.

## Existing foundation and concrete gaps

| Area | Reuse | Work needed |
| --- | --- | --- |
| Game rules | [RunEngine](../game/headless/run/engine.py), isolated encounters, catalogs, seeded RNG, declared native starts | Broader campaign-state coverage where evidence calls for it |
| Actor boundary | [HeadlessAdapter](../game/agent/headless/adapter.py), `full_run_v2`, exact candidate bindings, immutable combat summary | New measurements only for objectives beyond combat components and canonical run victory |
| Gym | [FullRunEnv](../game/agent/gym_env.py), [CombatTrainingEnv](../game/agent/training/env.py), separate task objectives, masks and cutoff handling | Broader populations only after measured progress |
| Data | [Canonical recorder](../game/agent/recording.py), [training sidecars](../game/agent/training/records.py), [task loader](../game/agent/training/dataset.py), [full-run corpus](../game/agent/training/run_corpus.py), compact PPO rollouts | Better public demonstrations where measured behavior calls for them |
| Execution | [Runner](../game/agent/runner.py), [workers](../game/agent/workers.py), frozen checkpoint loading, [persistent PPO collectors](../game/agent/training/parallel.py) | Choose worker count and rollout horizon for the measured task |
| Learning | Public graph features, shared candidate scorer, combat/campaign imitation and PPO, checkpoints, paired evaluation | Act 1 clear rate, selector completion and combat strength |

The [full encoder](AGENT_ENCODING.md#full-run-profile-and-environment) allocates
6,789,184 bytes per padded observation. The milestone 1 baseline below measures
the actual simulation/dispatch, projection, encoding and recording costs for
combat episodes. These are workload-specific observations, not estimates of
neural training throughput. Milestone 3 measures a real CPU training batch below.

## Implementation boundaries

Keep game rules in `game/headless/`. New learning code belongs under
`game/agent/training/`, with installed commands in `game/cli/`. Proposed module
names below describe responsibilities; create them as their milestone needs them.

| Responsibility | Proposed location |
| --- | --- |
| Validated experiment configuration and scenario sampling | `game/agent/training/config.py`, `scenarios.py` |
| Combat task lifecycle and public transition measurements | `game/agent/training/env.py`; narrowly shared adapter helpers if needed |
| Reward component registry and evaluation | `game/agent/training/rewards.py` |
| Task sidecars, objective validation and offline rescoring | `game/agent/training/records.py`, `dataset.py` |
| Public feature extraction and candidate-scoring network | `game/agent/training/features.py`, `model.py` |
| Imitation/PPO updates and bounded collection | `game/agent/training/learner.py`, `ppo.py`, `rollout.py`, `parallel.py`, `ppo_run.py` |
| Checkpoints and comparison reports | `game/agent/training/checkpoint.py`, `evaluation.py` |
| Curriculum and frozen paired benchmarks | `game/agent/training/curriculum.py`, `curriculum_run.py`, `benchmark_suite.py`, `benchmark.py`, `comparison.py` |
| Full-run task, demonstrations, transfer and evaluation | `game/agent/training/run_task.py`, `run_corpus.py`, `run_demonstrations.py`, `run_evaluation.py` |
| Installed entry points | `game/cli/agent_train.py`, `agent_evaluate.py`, `agent_play.py` |

Use an optional `train` dependency extra containing a tested PyTorch/Gymnasium
stack. Preserve the standard-library engine and ordinary agent imports. Verify
Python 3.10 compatibility when selecting dependency versions; record exact versions
for experiments. Start with CPU as the reference execution mode. Device selection
can support available accelerators after the same numerical checks pass.

Actor and critic inputs contain only the public decision and its observable
history. Dispatch bindings, engine snapshots, seeds, RNG state, scenario registry
indexes and private replay metadata stay with the controller. Outcome labels and
rewards arrive after actions and never become pre-action hindsight features.

## Milestone 1: combat episodes and a measured baseline

Create a `CombatTrainingEnv` consumer using a fresh `RunEngine` and the existing
`HeadlessAdapter(..., decision_profile="full_run_v2")`. Reuse dispatch, validation,
identity and encoding machinery. Extract shared lifecycle helpers only where the
existing Gym implementation would otherwise need to be copied.

Start with a named Ironclad/A0/Overgrowth scenario set: ordinary starter inventory,
representative weak and normal encounters, and separate train/development/test
seed schedules. Use the existing native RNG profile explicitly; bare custom runs
otherwise default to fixture RNG. Initialize relics, potions, upgrades and decks
through existing game-owned APIs. Label authored starts as controlled scenarios.
Campaign-derived starts are a later addition and retain separate provenance.

Define the episode boundary precisely:

- Include play, target, end-turn, potion and nested selection decisions owned by
  the same fight. Do not end the episode merely because a selector changes the
  public context kind. Never hand a nested choice to an automatic fallback.
- End on the authoritative completed fight after automatic cleanup and synchronous
  end-of-combat hooks, before reward claims or another post-combat choice. Verify
  death/revival, escaping enemies and delayed resolution against engine outcomes.
- Return task termination on combat win/loss. Keep the underlying run outcome
  separate: winning a fight is not `sts_run_outcome_v1: victory`.
- External time/decision budgets truncate and retain the final public decision
  for bootstrapping. Failures remain failures; invalid/stale commands neither
  advance training nor receive rewards. Do not retry uncertain mutations.

Add a small immutable public transition summary for the controller. Capture the
completed combat's identity/outcome before losing its ownership reference, and
read only allowlisted public values after `RunEngine.apply` returns. Record final
HP/max HP after automatic end-of-combat effects and before reward choices. This
endpoint is necessary because `RunOutcome` currently has no final HUD state and
`finish_combat()` clears `run.combat`. Do not infer victory from an empty enemy
list, or infer cumulative damage taken from net HP change. No engine snapshot or
private effect-resolution dictionary enters the summary.

Use public decisions from the same owner for both fixed Gym encoding and the
later packed training representation. A narrow owner API may expose terminal
facts to training without changing the existing decision/outcome wire schemas.
Retain the current `StsEnv` and `FullRunEnv` defaults.

**Acceptance:** focused cases exercise normal victory, defeat, a nested selector,
a potion child, revival and an external cutoff; terminal facts and flags agree
with the engine. Identical seeds/actions reproduce traces and independent episodes
do not share mutable state. Report random-legal and current-heuristic performance
and the time spent in simulation, projection, encoding and recording.

### Milestone 1 usage and implementation choices

Install the existing optional `gym` extra; this milestone needs no PyTorch or
new dependency extra. Ordinary engine, adapter and training-package imports
remain standard-library only. The optional environment uses the existing full
encoder and its 2,048 candidate slots:

```python
from game.agent.full_policy import choose_action
from game.agent.training.env import CombatTrainingEnv

with CombatTrainingEnv(encounter="overgrowth_nibbit") as env:
    observation, info = env.reset(seed=42)
    while True:
        decision = env.public_state
        candidate = choose_action(decision)
        observation, reward, terminated, truncated, info = env.step(
            env.action_index(candidate))
        if terminated or truncated:
            print(info["combat"], info["outcome"])
            break
```

`action_index` maps a candidate object from the current `public_state` to its
encoded action slot without re-encoding. Public-list positions are not Gym action
indices. If selecting from `env.encoder.decode(observation)` instead, that
decoded list is already in encoded order and its index can be passed directly.

`public_state` exposes the immutable structured decision used by the encoder,
without a binding or engine reference. Combat ownership, rather than a context
label, determines the endpoint. `info["combat"]` is the controller's allowlisted
`sts_combat_summary_v1`: attachment-local combat reference, ongoing/victory/defeat,
HP, max HP and turn. Terminal HP includes synchronous post-combat effects. It
contains no seed, engine identity, snapshot or effect-resolution dictionary.

The milestone 1 task reward, retained as the default, is +1 for a combat win and 0 otherwise.
A fight win returns `terminated=True` while `info["outcome"]` normally describes
an unfinished run cut off with `truncated/external_stop`. A real defeat preserves
the real run defeat. The terminal encoded state has no legal actions; time and
decision cutoffs instead retain the final public decision and legal mask, with
`truncated=True`. Rejected actions do not advance the episode or pay rewards;
execution failures require reset. Milestone 2 below adds configurable rewards
and training sidecars. Existing `StsEnv` and `FullRunEnv` rewards/defaults are unchanged.

The named scenario set `ironclad_a0_overgrowth_v1` contains Nibbit, Fuzzy Wurm and
Slimes weak encounters, plus Mawler, Nibbits and Cubex normal encounters. Each
starts a fresh native-RNG Ironclad A0 run with 80/80 HP, its ten starter cards,
Burning Blood, no upgrades and no potions, using game-owned setup APIs. These
are controlled starts, not campaign-derived states. `engine_factory(seed)` can
supply another fresh, exclusively owned live combat for controlled experiments.

Run both reference policies on paired development cases:

```bash
sts-agent-evaluate --output-dir runs/combat-baseline --cases-per-scenario 4 \
  --split validation --max-decisions 256 --time-limit 30
```

The command currently evaluates `random_legal` and the unchanged public heuristic;
it does not load learned checkpoints. Four seeds for each of six encounters
produce 24 episodes per policy. Use a new output directory for each experiment:
completed reports/trajectories are never overwritten. `--encounter` can select a
subset; `--start-index` selects a window of the trusted seed schedule. The existing
`validation` split means development/model selection. Train, validation and test
use disjoint external seed schedules; Gym game-seed generation and policy RNGs
are separate. The default evaluation leaves held-out test seeds unused.

`baseline.json` contains source/build/policy identities, software versions,
limits, paired episode IDs, actual combat/run outcomes, HP, action counts,
win rates with Wilson intervals, per-encounter summaries and timings. Every
completed episode has a canonical `.trajectory.jsonl` with its original sparse
run rewards (a combat win pays 0 there). Private replay configuration and seeds
live in the separate owner-only `runs/combat-baseline-private` directory.
Milestone 2 adds a separate `.training.json` per completed episode and records
resolved objectives/components in the version 2 evaluation report.

Timings distinguish initialization, action dispatch including simulation and
guards, public projection including its guard, fixed encoding, policy choice,
and canonical recording. Total wall time also includes array copies and replay
audit writes. Each padded observation occupies 6,789,184 bytes; compact learner
storage remains milestone 3. Infrastructure failures stop the batch, leave
unfinished trajectories `.partial`, and remain visible with the unattempted count
in a failed report. These are baseline measurements, not evidence of learning.

### Milestone 1 accepted results — 2026-09-28

The [retained public report](evidence/combat_baseline_2026_09_28.json) records the
final source fingerprint, runtime versions, paired episode results and timings.
Both policies played the same 24 development cases (four per encounter). The
final measurement ran without concurrent test execution; no held-out test cases
were used. All 48 episodes completed without cutoffs or infrastructure failures.

| Policy | Combat wins | Mean final HP on wins | Decisions/second, including recording |
| --- | ---: | ---: | ---: |
| Random legal | 14/24 (58.3%) | 52.50 | 22.23 |
| Current public heuristic | 22/24 (91.7%) | 64.91 | 20.07 |

The 1,009 decisions took 47.51 seconds of summed episode wall time: 2.14 seconds
in simulation/dispatch, 10.66 in projection, 16.30 in encoding, 14.83 in recording,
and 3.15 in policy choice; initialization and remaining overhead make up the rest.
These controlled starter-deck fights establish a small baseline, not campaign
strength or evidence of learning. Wilson intervals in the report describe this
small sample and do not establish general policy strength.

All 48 canonical trajectories were reloaded and validated against their final
source/policy fingerprints; their 1,009 original sparse rewards remain zero.
Full trajectories and private replay audits are retained locally under
`runs/combat-milestone1-20260928-verified` and its `-private` sibling. Trajectory
filenames in the retained report refer to that original output directory.

Validation: the full agent suite passed **424 tests in 610.51 seconds**. A final
explicit v1-profile rejection guard passed the focused combat/adapter suite
(**66 tests in 5.07 seconds**). Compilation of `game` and `tests`, Python 3.10
syntax checks, standard-library-only core imports, the installed command and its
missing-Gym error were checked. Runtime testing used Python 3.11.15,
Gymnasium 1.0.0 and NumPy 2.4.6. One independent semantic review passed, including
zero-action timeout and no-clobber checks. The only suite warnings were the
existing Gym checker warnings for fixed-value observation bounds.

Available delivery timings: initial implementation and focused checks occupied
approximately 18:37–18:50 UTC; the full regression pass took 10m 10.51s; the local
editable package install took 0.66s. Review, documentation and validation
overlapped; review and user-wait durations were not separately measured. The
final baseline duration above is a measured workload, not a training estimate.

## Milestone 2: configurable objectives and faithful records

Implemented with a versioned `RewardSpec` and a pure calculation over the public
action, reconciled report and before/after combat summaries. JSON configuration
accepts finite numeric weights and registered component names; unknown or
unavailable components fail explicitly, even at zero weight. Reward calculation
does not mutate the engine or consume game RNG.

Keep three concepts distinct: actual run outcome, combat-task outcome, and the
scalar training reward. Preserve the existing full-run base reward in recordings.

| Initial component | Exact measurement | Initial weight |
| --- | --- | ---: |
| `combat_win` | 1 once at genuine combat victory | 1.0 |
| `combat_loss` | 1 once at genuine combat defeat | 0.0 |
| `win_hp_fraction` | On victory only, final HP divided by final max HP at the declared endpoint, bounded to [0, 1] | 0.0 |
| `end_turn_action` | 1 for a reconciled `end_turn` command; nested selector actions do not increment it | 0.0 |
| `potion_use_action` | 1 for a reconciled `use_potion` command, irrespective of later belt replacement | 0.0 |

The last component measures the decision to use a potion, not an inferred count
of net potions consumed. Additional objectives such as exact damage prevented or
resource consumption need their own public measurement and focused tests before
they become selectable. A zero weight does not justify inventing a missing value.

The checked-in [default configuration](../configs/training/combat_victory.json)
is accepted by `sts-agent-evaluate --config`:

```json
{
  "mode": "combat",
  "scenario_set": "ironclad_a0_overgrowth_v1",
  "reward": {
    "schema": "sts_training_reward_v1",
    "weights": {
      "combat_win": 1.0,
      "combat_loss": 0.0,
      "win_hp_fraction": 0.0,
      "end_turn_action": 0.0,
      "potion_use_action": 0.0
    }
  }
}
```

Omitted weights retain the defaults above; resolved configurations always record
all five. Duplicate/unknown keys, unsupported versions/modes/scenario sets,
booleans, non-finite weights and unavailable components reject. The immutable
specification identity hashes its version and normalized weights, independently
of JSON key order.

The default optimizes fight victory probability. Experiments can add, for example,
a small positive terminal HP weight or a negative potion-use weight. Those weights
define a different training utility; win rate and HP remain separately reported.
Changing weights affects further training, not the behaviour of an already frozen
checkpoint. Goal-conditioned inference is outside the first implementation.

`sts_public_trajectory_v1` and its sparse reward validator remain intact. A successful
isolated combat ends its still-running canonical run recording with the existing
`truncated/external_stop` outcome; its training task has terminated successfully.
A real defeat keeps its real run outcome. The versioned training sidecar is keyed
by trajectory digest and transition index for reward components, `RewardSpec`,
task flags and the public terminal summary. It reuses canonical observations
instead of duplicating them in another dataset. The loader validates joins and
permits recomputing supported reward weights from those measured components. It uses
the sidecar's task flags and training reward; existing loaders continue to return
the original run flags and sparse reward.

For online learning, hold compact transitions in memory and retain selected
complete audit episodes with the same semantics. Never publish partial episodes
as complete data, overwrite original sparse rewards, or mix incompatible reward
specifications in a value-learning batch without an explicit conversion.

**Acceptance:** hand-calculated traces match component totals; terminal reward is
paid once; rejection/reset/truncation cannot manufacture success. Test healing,
HP costs, replacement potions and selector toggles against the declared meanings.
Old recordings still load unchanged. Reward sidecars reject mismatched digests,
duplicate transitions, missing measurements and incompatible task boundaries.

### Milestone 2 usage and record semantics

For example, copy the default JSON to a new experiment configuration and set
`win_hp_fraction` to `0.25` and `potion_use_action` to `-0.02`. Pass that file with
`--config`, or construct the same objective directly:

```python
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.rewards import RewardSpec

objective = RewardSpec({"win_hp_fraction": 0.25, "potion_use_action": -0.02})
env = CombatTrainingEnv(reward_spec=objective)
```

The spec is fixed for an environment's lifetime. Each reconciled step returns
the scalar reward and `info["training_reward"]` containing `spec_id`, all five
measured `components`, and `total`. Reset, rejected actions and cutoffs before
dispatch return no measurement and reward zero. They cannot fabricate a victory
bonus. Nested selection/toggle/confirm commands are separate transitions and
count as neither end turns nor potion use. Consuming a potion that replaces or
refills the belt still contributes one potion-use command. Final HP fraction
includes HP costs, max-HP changes and automatic post-combat healing.

`CombatTrainingRecorder` wraps the existing canonical writer and buffers only
compact measurements. Each `.training.json` has schema `sts_combat_training_v1`:

- The exact canonical file SHA-256 **including the completion footer**, opaque
  episode ID, task kind and resolved reward specification/identity.
- An initial public combat summary and one indexed row per reconciled canonical
  transition: all five components, scalar reward, task flags and combat summary.
- An explicit final task boundary. A zero-action timeout has no fake transition;
  a timeout between actions marks the last recorded transition truncated without
  changing its reward or successor decision.

The compact summaries have the same allowlist as `info["combat"]`. Ongoing HP,
max HP and combat round are cross-checked against public observations. Final HP
is attested by the combat owner because canonical terminal outcomes do not carry
HUD values. This is a consistency/digest check, not independent proof against a
producer falsifying terminal facts. Private replay seeds and engine state never
enter the sidecar or actor observations.

Publication is canonical-first, sidecar-second. Each file uses an exclusive
`.partial`, flush/fsync and atomic no-clobber publication. Interruption between
them can leave a valid canonical file without a published training sidecar; the
training loader rejects that incomplete pair. Existing canonical readers still
load that file and retain their original sparse reward/run flags.

Load a pair or explicitly rescore supported components without replaying a game:

```python
import json
from pathlib import Path
from game.agent.training.dataset import load_training_dataset
from game.agent.training.rewards import RewardSpec

root = Path("runs/combat-baseline")
report = json.loads((root / "baseline.json").read_text())
pairs = [(root / row["trajectory"], root / row["training"])
         for row in report["episodes"] if row["status"] in ("terminated", "truncated")]
for episode in load_training_dataset(pairs, split="validation"):
    print(episode.reward_spec.identity, sum(step.reward for step in episode.transitions))

# Explicit conversion to one objective, leaving original files unchanged.
rescored = load_training_dataset(pairs, split="validation",
    reward_spec=RewardSpec({"combat_win": 0, "win_hp_fraction": 1}))
```

`load_training_episode(trajectory_path, sidecar_path, split=...)` validates one
complete pair. `load_training_dataset` preflights compact objective identities
before yielding its first episode and rejects mixed specs unless the caller
supplies one explicit conversion. Each episode retains `recorded_spec` alongside
the effective `reward_spec`. Original measurements/rewards must validate even
when rescoring. File contents never supply paths to the loader. Full observations
are loaded one episode at a time; compact sidecars are held for batch preflight.
Use trusted local evaluation manifests when constructing the explicit pairs above.

`game.agent.training.dataset.training_examples(..., encoder=FullRunEncoder())`
encodes the same canonical public observations with task rewards/flags and a
`reward_spec_id` sample label. That label is not an observation feature. Genuine
combat termination disables value bootstrapping even though the run was cut off;
ongoing time/decision cutoffs keep their public successor and legal mask.

The `sts_combat_baseline_v2` report and `sts_combat_replay_v2` private audit retain
the resolved configuration and objective identity. Reports add component totals
and mean training return while keeping win rate, HP and actual run outcomes
separate. Historical milestone 1 reports and trajectories remain unchanged;
they contain no training sidecars and are not silently upgraded. No learner,
checkpoint or online rollout buffer is introduced in this milestone.

### Milestone 2 accepted results — 2026-09-28

The affected regression run passed all **221 behavior checks** (new reward/data
cases plus combat, canonical recording, runner, Gym and adapter consumers).
That 83.18-second run also exposed a stale package inventory missing the milestone
1 evaluation CLI. The inventory was updated, and all **4 package/import checks**
passed in 0.31 seconds, including `--config` help and reward/config/data imports
with optional dependencies disabled. Compilation, Python 3.10 syntax checks and
diff/link checks passed. The earlier full campaign/engine acceptance was not
rerun for this consumer-only change.

One independent read-only semantic reviewer found no blockers. Its controlled
checks covered shaped terminal reward, unchanged canonical rewards, mixed-objective
rejection, explicit conversion, footer-bound digests, pre-dispatch timeout and
cancellation between the two publications. The focused tests additionally cover
HP costs, post-combat healing, max-HP changes, potion belt replacement, selector
toggles, malformed components, task-boundary tampering and publication races.

The installed `sts-agent-evaluate --config` command completed one paired Nibbit
development case, **2 episodes / 27 reconciled decisions**, under weights
`combat_win=1`, `combat_loss=-1`, `win_hp_fraction=0.25`, `end_turn_action=-0.01`
and `potion_use_action=-0.02`. The [retained public report](evidence/combat_rewards_2026_09_28.json)
records both wins: random-legal ended at 57/80 HP after five end turns for return
**1.128125**; the heuristic ended at 73/80 after two end turns for **1.208125**.
Both canonical returns remain zero. This small integration smoke establishes
scoring/recording agreement; the milestone 1 sample remains the performance baseline.

Online returns and all saved component totals matched the training loader.
Explicit offline conversion to the default objective returned **1.0** for each
fight and left every source file byte unchanged. All **48 milestone 1 episodes /
1,009 transitions** loaded with their original metadata/rewards; the retained
milestone 1 report still matches its original file byte for byte. Full local
smoke artifacts are under `runs/combat-milestone2-20260928-shaping/`, with private
replay audits in the disjoint owner-only sibling directory.

The smoke's shipped-source build identity is
`75b6905253a48a7c5d88dbf774b505af7cee97cd760a558d3121c5245981299e`.
Measured episode wall time totalled **1.419 seconds**. Implementation, review,
documentation and checks overlapped approximately **19:08–19:37 UTC**; review
duration was not separately measured. The existing editable installation exposed
the updated command; no new package build or user setup wait was needed.

## Milestone 3: learnable representation, imitation and checkpoints

Implement a small PyTorch actor-critic with a shared public state encoder. Encode
typed scalar fields, public content/mechanic names, entity links and ordered
children. Pool entity/state features and score each candidate using the state,
action kind, subject embedding and target embedding. Use a shared scorer over
all candidates, not a fixed interpretation of slot numbers. A separate value head
predicts expected return under the selected reward specification; only the pure
terminal-victory objective makes that return a victory probability.

Use a versioned feature schema and frozen vocabulary with explicit unknown-name
handling. Per-observation string-table indexes and raw entity ordinals are not
content IDs. Preserve availability markers, duplicate entities, hand/orb order,
selection bounds and the links needed to evaluate every legal candidate. Start
with a feed-forward encoder over the available public history; add recurrence
only if a measured learning limitation justifies it.

First prove one real forward/backward batch using the existing full encoding.
Then pack populated graph rows and candidate tables for rollout storage and
minibatches, preserving public values and exact candidate dispatch mappings.
Share traversal/canonicalization with the current encoder, and compare packed
and fixed representations. Do not silently clip cards, history or candidates to
meet memory limits. Avoid allocating the full padded graph at every stored step
or applying global quadratic attention over all serialized rows.

Apply the same legal-action mask during sampling, log-probability calculation,
entropy calculation and evaluation. Terminal observations are not sent through
an all-masked categorical distribution. Changing candidate enumeration or public
reference names must not change the corresponding action probabilities.

Use a small corpus from the current public chooser for a behaviour-cloning
warm-up. Include combat selections and potion decisions. Demonstrate that a tiny
set of distinguishable choices can be overfit; report held-out imitation accuracy
and episode performance. The teacher is an integration policy, not an expert.
Keep a no-imitation baseline for the later PPO comparison.

Save an inference bundle containing model weights, architecture, feature/vocabulary
identity, contract profile, reward identity and code/build provenance. Keep private
resume data separate. Initially support checkpoints at clean episode/collector
boundaries: optimizer state, learner RNGs and sampling cursor are recoverable,
while interrupted in-flight episodes are explicitly abandoned. Do not claim exact
mid-combat resume, which the public adapter does not currently support.

**Acceptance:** finite forward/backward updates, decreasing imitation loss, zero
invalid dispatches, candidate/reference invariance and duplicate-card coverage.
Reloading a checkpoint reproduces inference on a fixed corpus. A bounded CPU
resume experiment matches uninterrupted execution at the supported boundary.
Report batch memory, encoding cost and inference/update latency.

### Milestone 3 usage and implementation choices

Implemented under `game.agent.training` with the optional `train` extra. The
tested environment uses Python 3.11.15, PyTorch 2.13.0, NumPy 2.4.6 and Gymnasium
1.0.0 on CPU with one PyTorch thread. PyTorch's installed metadata permits Python
3.10+; source syntax is also checked for 3.10. A Python 3.10 interpreter was not
used for this acceptance run.

```bash
python -m pip install -e '.[train]'
sts-agent-train collect --output-dir runs/demos-train --split train
sts-agent-train collect --output-dir runs/demos-validation --split validation
sts-agent-train imitate --train-dir runs/demos-train \
  --validation-dir runs/demos-validation --output-dir runs/imitation --updates 128
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model \
  --output-dir runs/imitation-combat --cases-per-scenario 1
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model --hybrid \
  --output-dir runs/imitation-campaigns --campaign-cases 2 --time-limit 60
```

Each command publishes to a new output directory and keeps existing artifacts.
`collect` records eight controlled scenarios per case: the six milestone 1
encounters plus native Armaments/Gambler's Brew selectors and low-HP potion use.
It uses the unchanged public heuristic. Collection remains bounded by decisions
and time. These authored starts are not campaign-derived training data.

The default network has 48 hidden units and two graph message-passing layers.
Typed scalar features, frozen public-name embeddings, parent/child order and
typed entity links feed pooled state/entity representations. One shared scorer
handles every candidate; a separate value head fits complete-episode returns.
Unknown names have ID 0; validation/test corpora cannot fit a vocabulary. Exact
public values and dispatch mappings remain in populated tables from the shared
encoder. Scalar scaling/log transforms are explicitly lossy model features.
Every policy probability, sample, entropy and greedy decision uses the same legal
mask; terminal observations have no categorical distribution.

Imitation uses cross-entropy and a value MSE with weight 0.25, Adam learning rate
0.003, batch size 8 and gradient clipping at 1.0. Complete returns use gamma 1.
Cutoff demonstrations supply policy labels but no invented terminal value label.
The warm-up's value targets were all victories, so its small value error does not
demonstrate calibration or victory prediction on unfamiliar states. The value
head is unconstrained; its numerical output need not lie in [0, 1].

`imitation.json` records settings, corpus/vocabulary identities, initial/final
bundle hashes, train/validation losses and accuracy, per-update metrics, input
tensor bytes and timings. `initial.sts-model` retains the no-imitation baseline;
`final.sts-model` contains the completed warm-up. Each inference archive contains
only `manifest.json` and a model `state_dict`: architecture, contract/layout,
feature vocabulary, reward identity, build provenance, runtime and static learner
settings accompany the weights. Loading uses PyTorch's
[weights-only state-dictionary path](https://docs.pytorch.org/tutorials/beginner/saving_loading_models),
checks exact keys/shapes/dtypes and rejects nonfinite weights or incompatible
identities. No model object is unpickled.

Private `*.resume.pt` files in the sibling `OUTPUT-private` directory retain
Adam moments, learner RNG, shuffled example order and cursor. Resume validates
the bundle, objective, corpus, source build, Python/PyTorch/thread settings and
optimizer configuration. Files use mode 0600 and their directory 0700. Resume
supports the same CPU runtime between complete offline updates over a completed
corpus; it does not restore an in-flight game, guarantee cross-machine numerical
identity or continue a partially failed optimizer step.

```bash
sts-agent-train imitate --train-dir runs/demos-train \
  --validation-dir runs/demos-validation --output-dir runs/imitation-resumed \
  --resume-bundle runs/imitation/final.sts-model \
  --resume-state runs/imitation-private/final.resume.pt --updates 32
```

Here `--updates` is additional work. Omit `--seed`; saved RNG state is restored.
Explicit architecture, batch-size or learning-rate overrides must match the saved
settings. Interrupted collection is abandoned; collect a fresh bounded episode.
Checkpoints and reports publish atomically without replacing completed files.

The retained [milestone 3 report](evidence/imitation_training_2026_09_28.json)
records the bounded warm-up, combat and hybrid gameplay, memory/latency profile,
resume experiment and validation. Its development results do not consume held-out
test seeds or establish reliable gameplay strength. Detailed results are below.

The accepted local model is
`runs/imitation-milestone3-model-20260928-verified/final.sts-model`; its initial
baseline is beside it and private resume files are in the `-private` sibling.
The retained report identifies each demonstration, gameplay and profiling output
directory and original report hash. Binary models and full trajectories stay in
ignored `runs/`; the public evidence summary is retained in `docs/evidence/`.

The accepted warm-up used eight completed training fights (226 decisions) and
eight separate development fights (192 decisions), including six selected-card
actions, one selector confirmation and two potion-use actions in training.
After 128 updates, training cross-entropy fell **1.284 → 0.130** and action
agreement rose **25.7% → 98.2%**. Development agreement rose **26.6% → 92.2%**;
development cross-entropy was 0.324. The whole fit, including corpus loading and
publication, took **15.83 seconds**. A four-choice controlled test also reaches
100% agreement; it is an overfit check rather than game-performance evidence.

On six paired development combat cases, the checkpoint and heuristic each won
**6/6**, with mean post-hook HP **62.83/80**; random legal play won **3/6**.
All 18 episodes completed without cutoffs or infrastructure failures. The first
ordinary-HP hybrid campaign comparison used two fixed development cases with a
256-decision/60-second limit per run:

| Development pair | Heuristic | Learned combat / heuristic elsewhere |
| --- | --- | --- |
| 1 | Defeat; Act 1, floor 14; last HUD 3/80 HP; 5 potion-use actions | Defeat; Act 1, floor 16; last HUD 4/80 HP; 5 potion-use actions |
| 2 | Defeat; Act 1, floor 12; last HUD 14/80 HP; 1 potion-use action | Defeat; Act 2, floor 21; last HUD 4/87 HP; 5 potion-use actions |

These are the last public HUD values before terminal outcomes, not final HP;
every run ended in genuine defeat. There were no cutoffs, failures or invalid
dispatches in these campaigns or the combat comparison. Two campaign cases are
development feedback, not statistically persuasive evidence of an improvement.

A separate installed-command smoke ran the frozen checkpoint in two spawned
workers, each deliberately limited to 16 decisions. Both published valid
`decision_budget` truncations and 32 reconciled commands in total. One run exposed
a real policy gap: an unfamiliar `regent_cosmic_indifference` selector led to
repeated select/deselect actions instead of confirmation. These legal actions
stayed within the owning combat and the budget stopped the loop. This remains
recorded development evidence for broader selector training and PPO; the warm-up
is not a generally reliable combat policy.

The training corpus stores **35.94 MB** of packed tables plus neural features
(mean **159 KB/decision**, versus **6.79 MB** for one padded observation).
A representative batch of eight uses **229,552 bytes** of input tensors;
autograd retained **4,806,874 bytes** of unique tensor storage, including shared
inputs/parameters. Parameters, gradients and Adam tensors occupy 232,520,
232,520 and 465,176 bytes respectively. The profiling process peaked at 381.81 MB
RSS including libraries, corpora and multiple learner instances; this is not a
claim about minimum learner memory.

Across 32 development decisions, median feature encoding took **21.37 ms** and
complete greedy policy inference including encoding **21.85 ms**. Median update
latency was **3.54 ms** (preencoded minibatches). Representation validation and
encoding dominate this small network's computation. These timings describe this
CPU, corpus and workload. Eight real-corpus updates also matched four updates,
checkpoint/reload and four more updates exactly for weights, learner RNG, order
and cursor; focused tests separately cross an epoch boundary.

Final validation passed **540 agent/package tests in 623.55 seconds**, plus
compilation and Python 3.10 syntax checks. The only three warnings were the
existing Gymnasium notices about fixed observation bounds. The installed training,
combat evaluation, hybrid evaluation and two-worker checkpoint playback commands
were exercised. One independent semantic review completed with no remaining
blockers after fixes to optimizer/config/source bindings, terminal rejection and
audit-directory forwarding. Its focused checks included 14 passing tests.

Available timing: implementation began **19:44 UTC**; implementation, review,
experiments and documentation overlapped through final validation at **20:30 UTC**
on 2026-09-28. The final regression pass took **10m 23.55s**, and the editable
package refresh took **0.56s**. Review duration was not separately measured;
there was no user setup wait. No live bridge build or installation was needed.

### Begin hybrid full-run evaluation with the first usable checkpoint

Once a combat checkpoint reloads and selects legal actions through the adapter,
begin bounded ordinary-HP Ironclad A0 campaign evaluations. The learned policy
chooses combat actions and their nested choices; the existing heuristic chooses
all other actions. Ownership, not just the context's label, determines the handoff.
Reuse the same public adapter and candidate dispatch, with a frozen checkpoint
throughout each evaluated run.

Start this during milestone 3 and continue at selected checkpoints throughout
milestones 4 and 5. Completion of combat PPO, curriculum tuning or a strong combat
benchmark is not a prerequisite. Label these results as hybrid-policy evaluation;
full-run learning still begins in milestone 6.

Compare the hybrid with the unchanged heuristic on fixed development campaign
seeds, keeping held-out test seeds separate. Report actual run outcomes, campaign
progress, HP and potion usage, plus cutoffs and failures. Use these comparisons
to check whether better isolated combat performance improves campaign survival
or exposes poor consumable use and unfamiliar-deck weaknesses. Early evaluations
provide development feedback, not evidence of reliable full-run victory.

## Milestone 4: a bounded masked PPO learner

Implement a small project-owned PPO loop in PyTorch around the candidate-scoring
model. This is the initial baseline, not a claim that PPO is optimal for this game.
Use the published [PPO objective](https://arxiv.org/abs/1707.06347) and consistent
[invalid-action masking](https://arxiv.org/abs/2006.14171); avoid introducing another
environment or a second set of game rules to fit a training library.

Store the sampled candidate mapping, original legal mask, old log probability,
value prediction, reward components and termination/truncation flags with each
rollout transition. Compute advantages/returns using the configured training
reward. Start with `gamma=1` for terminal win-probability objectives. Any changed
discount or shaping is an explicitly different experiment. Configure learning
rate, clipping, entropy/value weights, gradient clipping and batch sizes in the
experiment file; record the resolved values.

Bootstrap external cutoffs from the final observation, never from the next reset.
Stop advantage recursion at episode boundaries; bootstrap value and continuation
masks are different. True combat/run termination has zero bootstrap. This follows
the [Gymnasium time-limit semantics](https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/).

Start with one synchronous environment and batched updates. Reuse existing seed
separation, cancellation, failure handling and atomic publication. When profiling
supports multiple collectors, extend shared worker lifecycle helpers and carry
an explicit checkpoint/policy identity to every worker. Current `run_batch` does
not already provide this training capability. Freeze a policy version during each
collection batch so PPO never unknowingly mixes behaviour policies.

Stop on non-finite losses, bad masks, incompatible artifacts or uncertain engine
execution. Retain the last complete checkpoint and an explicit failure category.
Track wins, losses, cutoffs, each reward component, entropy, value error, policy
divergence, decisions/second and peak memory using ordinary experiment reports.

Suggested development bounds are 256 collected decisions for the first update
smoke and, after it passes, a pilot capped at 20,000 decisions or one hour,
whichever comes first. These are planning defaults, not runtime estimates or
authorization to start a run. Select larger budgets from measured throughput.

**Acceptance:** compare return/advantage calculations to small manually worked
trajectories; exercise true termination and truncation separately. A controlled
learnable combat case improves relative to its initial policy across repeated
learner seeds. Check cancellation, checkpoint/resume, and independent environment
RNGs. A successful optimizer step alone does not establish learning.

### Milestone 4 usage and implementation choices

The installed `ppo` subcommand initializes the existing public candidate model
from an inference bundle. Starting from milestone 3's imitation bundle loads its
weights and frozen vocabulary and creates a fresh PPO optimizer. The retained
untrained bundle can also initialize a separate comparison. The declared reward
must match the bundle's objective.

```bash
sts-agent-train ppo --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_ppo.json --output-dir runs/ppo \
  --decisions 256 --time-limit 120 --seed 17
sts-agent-evaluate --checkpoint runs/ppo/final.sts-model \
  --output-dir runs/ppo-combat --cases-per-scenario 1
sts-agent-evaluate --checkpoint runs/ppo/final.sts-model --hybrid \
  --output-dir runs/ppo-campaigns --campaign-cases 2 --time-limit 60
```

The resolved `sts_ppo_experiment_v1` configuration contains the training objective,
named encounters and PPO settings. The supplied configuration starts with the
existing ordinary-HP Nibbit encounter and sparse combat victory reward. Defaults
are 256 decisions per rollout, at most 96 per fight, gamma 1, GAE lambda 0.95,
Adam learning rate 0.0003, 32-example minibatches and four epochs. Policy clipping
is 0.2, entropy weight 0.01, value-MSE weight 0.5 and gradient clipping 0.5. A
post-epoch approximate-KL check stops additional epochs above 0.03; this is a
stopping heuristic and does not guarantee a hard divergence bound. Advantage
normalization uses population variance and retains the signal for singleton or
constant batches. Changing these settings declares a different experiment.

The synchronous learner freezes one model throughout a rollout, using one local
collector by default or persistent processes with `--workers`. Sampling,
likelihoods, entropy and update replay all use the original legal candidate mask
and mapping. The last unfinished fight closes at the rollout decision limit;
its final public observation supplies the bootstrap value. A true combat win or
loss uses zero bootstrap, even though the canonical run record for a combat win
ends with `external_stop`. GAE recursion stops at either task boundary. A timeout
before dispatch adds no fictional action and cannot trigger an endless reset loop.
Each collector closes every environment before optimization; it does not retain
live games across batches.

`ppo.json` records resolved configuration, source/runtime identities, initialization,
actual wins/losses/cutoffs/failures, accepted and trained decisions, reward components,
HP, potion use, update losses, entropy, value error, divergence, input memory,
parent-process peak RSS, worker allocation and throughput. Parent RSS excludes
collector processes; it is not total pool memory. `rollout-NNNNN.json` retains original candidate
references/masks, selected action, old likelihood/value, next value, rewards,
task flags and computed advantages/returns. It joins public canonical trajectories
and training sidecars by episode ID and trajectory digest. Private replay audits
retain engine reset seeds separately. These are controlled headless starts.

Unrestricted PPO inference bundles use `sts_inference_bundle_v2`; the
[filtered action policy](#shared-policy-actions-and-selection-order) uses v3.
Both retain `ppo_v1` identities, and existing v1 imitation bundles remain loadable.
Each completed rollout/update boundary, including a recorded no-signal skip, publishes a bundle
and separate private resume file. `initial.sts-model` is published before collection,
`update-NNNNN.sts-model` after each complete update, and `final.sts-model` on clean
completion. The report names the last complete checkpoint. Public inference has
no optimizer, RNG or sampling cursor; its digest binds the matching private state.

```bash
sts-agent-train ppo --checkpoint runs/ppo/final.sts-model \
  --resume-state runs/ppo-private/final.resume.pt \
  --config configs/training/combat_ppo.json --output-dir runs/ppo-resumed \
  --decisions 256 --time-limit 120
```

`--decisions` means additional work and is bounded to 1–20,000 per invocation;
`--time-limit` is at most one hour. Resume restores Adam state, separate action
sampling and minibatch RNGs, episode cursor, decision count, collection iteration
and optimizer-step count. Private `sts_ppo_resume_v3` state binds the
[signal guard and skipped iterations](#ppo-signal-guard-and-three-learner-pilot),
as well as worker count and allocation schedule introduced by v2.
Omitted `--workers` restores the saved count; changing it
requires a new experiment from an inference bundle. Same-source legacy v1 private
states restore serial collection. Omit `--seed` and `--start-index` when resuming. Exact
continuation requires matching source, experiment and CPU runtime, and a boundary
after a completed rollout/update with no live game. Interrupted collection or a
partly applied update is abandoned. SIGINT/SIGTERM, deadline checks and numerical
or execution failures retain the preceding complete artifact and report the stop.
The deadline is cooperative at action/minibatch/measurement boundaries. Parallel
collection additionally enforces a parent deadline with five seconds of grace
for results; cancellation or failure uses bounded cooperative, terminate and kill
cleanup. A stopped invocation may have no `final.sts-model`:
use `last_complete_checkpoint` and its matching private file instead.

### Milestone 4 measured results

The retained [milestone 4 report](evidence/ppo_training_2026_09_28.json) binds the
source, configuration, reports and checkpoints. Models and complete trajectories
remain under ignored `runs/`. The accepted ordinary-combat checkpoint is
`runs/ppo-milestone4-pilot-20260928/final.sts-model`, with the matching private
resume state in `runs/ppo-milestone4-pilot-20260928-private/final.resume.pt`.

A controlled learning probe used the real engine and three fresh learner seeds,
with no imitation. Each one-action fight offers Strike, which wins, or end turn,
which loses. A 16-unit/one-layer network trained for 512 decisions per replicate,
in 64-decision batches, with learning rate 0.003, GAE lambda 1 and KL threshold
0.05. These settings and all three replicates were fixed before running. Evaluation
uses a separate RNG and 32 paired stochastic development trials of that same
authored fight before and after learning:

| Replicate | Initial wins | Final wins | Exact policy probability of winning, before → after |
| --- | --- | --- | --- |
| 1 | 21/32 | 32/32 | 58.68% → 99.51% |
| 2 | 10/32 | 32/32 | 34.81% → 99.90% |
| 3 | 11/32 | 32/32 | 37.39% → 99.75% |

All three improved. Here the exact probability is the policy probability of the
single winning action, not a value-head estimate. This demonstrates that the
learner can acquire the authored decision; it is not evidence of broad combat
strength. Training took 14.37, 14.21 and 14.33 seconds respectively; the complete
probe including evaluation/publication took 47.00 seconds. No held-out test set
was used.

The ordinary-combat pilot initialized the accepted milestone 3 imitation weights
and used the supplied PPO configuration. It completed **1,024 decisions in 81.94
seconds**, across four batches and 120 optimizer steps: **113 combat wins, no
defeats, three batch-limit cutoffs and no execution failures**, out of 116 attempts.
Mean post-hook HP on wins was 70.88/80. All 1,024 accepted decisions were trained;
no potion-use actions occurred. This is training-distribution behavior, not an
unbiased evaluation result. The first 256-decision development smoke also passed;
a subsequently fixed deadline edge case and its original source identity remain
distinguished in the evidence record.

The pilot averaged 12.50 decisions/second including recording and updates, with
525.48 MB peak process RSS. A packed 256-decision rollout occupied about 41.03 MB;
minibatch inputs peaked at 924,200 bytes. Collection took 79.44 seconds in total,
while the four updates took 2.29 seconds. This workload supports retaining the
simple synchronous collector for now; these numbers include this machine's
runtime and public-recording overhead. All losses and gradients were finite;
post-update approximate KL ranged from 0.0054 to 0.0651. The value targets are
dominated by victories on easy fights and do not establish calibration elsewhere.

On six paired development combat cases, PPO and the heuristic each won **6/6**;
random legal play won **3/6**. Mean post-hook HP was 63.33/80 for PPO and 62.83/80
for the heuristic. All 18 evaluation episodes completed without cutoffs or
failures. Milestone 3's imitation checkpoint also won all six of these same cases;
the small comparison does not establish improved general strength.

The same two development campaigns were also run with the unchanged heuristic
and with PPO handling combat, under 256-decision/60-second per-run bounds:

| Development pair | Heuristic | PPO combat / heuristic elsewhere |
| --- | --- | --- |
| 1 | Defeat; Act 1, floor 14; last HUD 3/80 HP; 5 potion-use actions | Defeat; Act 1, floor 16; last HUD 3/80 HP; 5 potion-use actions |
| 2 | Defeat; Act 1, floor 12; last HUD 14/80 HP; 1 potion-use action | Decision cutoff; Act 2, floor 19; last HUD 71/87 HP; 4 potion-use actions |

The second PPO campaign used a Colorless Potion and then alternated 29 selections
and 28 deselections of `the_gambit`, despite a legal confirmation candidate. Its
budget stopped the loop. This is a policy failure to make progress, distinct from
an invalid command or infrastructure failure. Compared with milestone 3's second
hybrid reaching floor 21 before defeat, this is a regression in that development
case. Narrow Nibbit training has not solved unfamiliar selectors or established
campaign improvement. There were no failed/invalid dispatches; the cutoff remains
in the report. HUD values above are last observed values, not terminal HP.

A separate installed playback smoke loaded the PPO bundle in two spawned workers
and recorded 32 reconciled decisions with two intentional 16-decision cutoffs,
in 2.27 seconds. This exercised frozen inference in existing workers; PPO training
at that milestone used one synchronous collector. Parallel training was added later.

Final validation passed **199 affected tests in 31.01 seconds**, including manual
PPO/GAE calculations, deadline crossing during final measurement, real task endings,
action-free timeouts, independent engine resets, original masks, exact CPU resume,
source/config/private-state mismatches, interruption after optimizer work, real
CLI SIGTERM, legacy imitation compatibility, records, runner lifecycle and package
help without optional dependencies. The single warning is Gymnasium's existing
fixed-bound `Box` warning. One unchanged long multi-act runner test and the wider
engine/profile matrix were not repeated; milestone 3 retains their earlier evidence.
Compileall and Python 3.10 syntax checks passed for all 432 Python sources/tests;
runtime validation used Python 3.11.15. One independent semantic reviewer found
the deadline gap, verified its correction, passed 16 focused checks and exercised
installed training/resume and no-clobber publication. No review blockers remain.

An additional 54.45-second artifact check reloaded all 116 pilot episodes and
recomputed the 1,024 saved action likelihoods, values and successor bootstraps
from the corresponding frozen checkpoints. Candidate mappings, masks, component
rewards, task flags, canonical sparse rewards, trajectory digests and private
permissions all matched. Total owner time through the evidence summary was about
43 minutes, including implementation, overlapping review, experiments and reporting;
separate implementation/review totals were not recorded.

Milestone 5 below freezes a larger evaluation population and broadens the training
curriculum, including selector completion and consumable choices.

## Milestone 5: combat evaluation and curriculum

Freeze the evaluation population and comparison rules before tuning. Keep seed
registries with the trusted evaluator; policy inputs contain only public state.
Separate training seeds, development seeds used for model selection and a held-out
test set used after selecting the checkpoint. Group derived starts by source
campaign to prevent one run from leaking across dataset splits.

Begin with 64 development and 256 held-out combat cases as practical planning
defaults, stratified across the declared scenarios. Compare random legal actions,
the current heuristic, imitation-only and PPO policies on the same cases. Run at
least three learner seeds for the selected configuration and report uncertainty;
these sample counts are not a strong-agent certification design.

Report combat win rate, HP remaining conditional on victory, starting-to-ending
HP change, potion-use decisions, turn count, cutoffs and infrastructure failures.
Keep failures and unfinished fights visible in denominators; do not silently
discard them. Report paired differences and confidence intervals, per encounter
and overall. Choose checkpoints using development gameplay metrics, with win rate
primary, rather than shaped return alone.

Expand the curriculum in bounded steps: weak/normal encounters; multiple legal
decks and starting HP levels; upgrades/relics/potions; elites/bosses; then starts
sampled from actual headless campaigns. Include held-out deck/encounter combinations.
Keep the evaluation distribution fixed while changing the training curriculum.
Exercise low-HP/HP-cost decisions, optional selectors and consumable tradeoffs so
the model cannot appear strong merely by exploiting one authored fight.

Continue the hybrid development evaluations started in milestone 3. Use their
results to identify combat objectives or training distributions that do not
transfer to campaigns, and to decide when to begin full-run learning. Exhausting
the combat curriculum is not a gate for milestone 6.

**Acceptance:** a reproducible report establishes whether the chosen checkpoint
improves on the heuristic under a predeclared criterion. A useful combat-policy
claim requires positive held-out evidence, not just successful software delivery.
If results are inconclusive, record that result and change one measured bottleneck
or learning assumption at a time; do not start an unbounded parameter search.

### Milestone 5 protocol and usage

The first curriculum experiment is predeclared before training: freeze
[64 development and 256 held-out starts](../configs/training/combat_benchmark.json),
then run three independently seeded PPO learners from the accepted milestone 3
imitation bundle. Keep its public feature vocabulary, network and terminal-win
objective unchanged. The [curriculum settings](../configs/training/combat_curriculum.json)
allocate **256, 256, 512, 256 and 256 decisions** to five cumulative stages per
learner (1,536 each; 4,608 total). Each stage has a 180-second limit; every combat
has at most 96 decisions and 30 seconds. Report actual stage coverage because a
decision budget can expire before every available start is visited.

The stages add ordinary starter-deck encounters; low-HP/HP-cost choices and an
upgraded strength deck; pending Armaments, Colorless Potion and Gambler's Brew
selectors plus consumables; an elite and boss; and the first two combats reached
through genuine ordinary-inventory campaigns. Starts use existing native game
APIs and snapshot restoration. The latter campaigns use the public heuristic to
reach the declared combat, without replacing failed origins. Reattaching at a
start begins a fresh public history. This covers early campaign fights, not the
distribution of later campaign states. The Choice/Fuzzy and Strength/Kin
combinations occur only in the held-out population.

Each stage carries inference weights and the frozen vocabulary, resets Adam and
its action/shuffle RNG, and continues the private episode cursor. A change of
curriculum is an explicit new experiment, not an exact resume across changed
settings. Exact resume remains available within an individual stage. Learner
seeds and replay/snapshot data stay in owner-only sibling directories; public
reports identify replicas and hash-bound artifacts.

```bash
sts-agent-evaluate --freeze-suite configs/training/combat_benchmark.json \
  --output-dir runs/combat-suite
sts-agent-train curriculum --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_curriculum.json --output-dir runs/curriculum
sts-agent-evaluate --suite runs/combat-suite/suite.json \
  --candidate imitation=runs/imitation/final.sts-model \
  --candidate ppo_1=runs/curriculum/learner-1/stage-4/final.sts-model \
  --candidate ppo_2=runs/curriculum/learner-2/stage-4/final.sts-model \
  --candidate ppo_3=runs/curriculum/learner-3/stage-4/final.sts-model \
  --output-dir runs/combat-development
sts-agent-evaluate --suite runs/combat-suite/suite.json \
  --select-development runs/combat-development/benchmark.json \
  --output-dir runs/combat-selection
sts-agent-evaluate --suite runs/combat-suite/suite.json --split test \
  --selection runs/combat-selection/selection.json --output-dir runs/combat-test
```

The evaluator restores the identical frozen engine start for each policy. It
includes random legal actions and the current heuristic automatically. Development
compares all three PPO finals and imitation; test compares only the selected PPO,
imitation and the two references. Selection ranks development wins first, then
fewer cutoffs, mean HP fraction conditional on winning and finally the policy
name. The test command binds this selection before opening any held-out snapshot;
the same suite then refuses further development evaluation or selection. Limits,
source identity, snapshot digests and policy artifacts must match their bindings.

Every planned case remains in the denominator, including failures, interrupted
and unattempted cases. Reports include overall and actual-native-encounter results,
authored scenario results, conditional winning HP, observed HP change, potion-use
commands, final combat turn and explicit cutoffs. Source failures stop evaluation
and prevent selection or a positive performance claim; no easier case replaces
them. HP-change metrics also report their observed count.

The predeclared primary comparison is **selected PPO minus heuristic held-out win
rate**. A positive claim requires a complete report and a positive lower bound
of its two-sided 95% source-group Hoeffding interval. Two fights from one campaign
share a group and cannot cross splits. For group sizes \(m_g\), total \(N\) and
\(\alpha=0.05\), the win-rate radius is
\(\sqrt{\log(2/\alpha)\sum_g m_g^2/2}/N\); the paired-difference radius is twice
that value. These conservative bounds permit dependence within a source group
and assume independent sampled sources. This is an application of
[Hoeffding's bounded-sum inequality](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf).
They describe the declared stratified population, not all game encounters or all
possible training seeds. Per-encounter intervals are descriptive, without a
multiple-comparison claim. Replica variation is reported separately on development.

After selection, continue the existing two-case hybrid development comparison at
256 campaign decisions and 60 seconds per case. Sparse win reward is unchanged:
training can finish a selector stochastically while greedy evaluation still
cycles. Record that failure if observed rather than introducing an undeclared
fallback or changing the objective after opening the held-out set.

### Milestone 5 measured results

The retained [milestone 5 evidence](evidence/combat_curriculum_2026_09_29.json)
binds the frozen suite, curriculum, three checkpoints, development selection,
held-out report and hybrid report. Full trajectories remain in the corresponding
local `runs/combat-milestone5-*-20260929` directories; private replay and resume
artifacts remain in their owner-only siblings. The accepted source build is
`96c280ae0446b970ff87dca8b42756d8f6c344f0779200a0458c545bbbe2c472`;
engine rules and heuristic identities are unchanged from milestone 4.

The fixed three-replica curriculum completed **4,608 decisions in 348.89 seconds**
on the existing CPU environment. Every learner visited every available profile
within each of its five stages, including the elite, boss and both early campaign
starts. Its 320 training episodes contained 298 wins, six defeats, 16 batch-quota
cutoffs and no infrastructure failures. Training included 39 selector confirmations,
39 potion-use commands and 26 deselections. These are sampled training outcomes;
they do not establish greedy policy strength.

Development evaluated all 384 planned case/policy pairs in **604.28 seconds**:

| Policy | Wins / 64 | Defeats | Cutoffs | Mean HP on wins |
| --- | --- | --- | --- | --- |
| Random legal | 36 | 28 | 0 | 45.81 |
| Heuristic | 60 | 4 | 0 | 56.12 |
| Imitation | 57 | 3 | 4 | 55.63 |
| PPO replica 1 (selected) | 60 | 3 | 1 | 56.08 |
| PPO replica 2 | 58 | 2 | 4 | 54.95 |
| PPO replica 3 | 56 | 4 | 4 | 56.89 |

There were no infrastructure failures or omitted cases. Across learner seeds,
development win rate averaged 90.625%, ranged from 87.5% to 93.75%, and had a
sample standard deviation of 3.125 percentage points. The selected replica tied
the heuristic overall but won four cases the heuristic lost and lost four cases
the heuristic won. Its paired interval was correspondingly inconclusive.

The profile breakdown explains the tie: the selected PPO won three of four
Gambler's Brew starts (imitation and the other two PPO replicas cut off on all
four), but only one of four Ceremonial Beast starts versus the heuristic's four.
It won all four low-HP potion starts versus the heuristic's one. Every learned
policy won the eight early campaign-derived development fights; that narrow
coverage does not establish late-campaign performance.

The locked selection is replica 1, bundle
`098b4d2c5d51da5f98af4c76179bb58cbfd93893f7be83d27d1931d8a6156691`.
The complete held-out evaluation ran **1,024 case/policy pairs in 1,440.99 seconds**:

| Policy | Wins / 256 | Win rate | Defeats | Cutoffs | Mean HP on wins |
| --- | --- | --- | --- | --- | --- |
| Random legal | 152 | 59.4% | 104 | 0 | 44.12 |
| Heuristic | 232 | 90.6% | 24 | 0 | 55.35 |
| Imitation | 231 | 90.2% | 19 | 6 | 54.76 |
| Selected PPO | 234 | 91.4% | 17 | 5 | 54.29 |

There were no infrastructure failures or omitted cases. Selected PPO won 14 cases
the heuristic lost and lost 12 that the heuristic won: **+0.78125 percentage
points**, with a source-group Hoeffding 95% interval of **−17.2248 to +18.7873
points**. The predeclared conclusion is **inconclusive**. The bounds are deliberately
conservative and too wide to establish a small improvement; this does not prove
the policies equivalent. Winning HP also did not improve in this sample.

All five PPO cutoffs were Gambler's Brew starts: 96 select/deselect commands with
no confirmation, still inside `discard_redraw`. It won 11/16 of these starts versus
imitation's 10/16 and the heuristic's 16/16. On the two excluded combinations, PPO
won 16/16 Choice/Fuzzy starts and 9/16 Strength/Kin starts; the heuristic won 16/16
and 11/16 respectively. Both won 9/16 authored Ceremonial Beast starts. The retained
report includes every native-encounter and authored-profile breakdown, including
HP change, potion-use commands and final combat turn.

The paired hybrid development check took **72.42 seconds**. Both selected-PPO
campaigns ended in actual defeat at floor 16 (Ceremonial Beast and Vantom), compared
with heuristic defeats at floors 14 and 12. There were no cutoffs or infrastructure
failures, and no learned full-run victory. Neither learned run used a Colorless
Potion or issued a combat selector command; the milestone 4 floor-19 Gambit loop
was not reached, so this check cannot establish that the earlier failure is fixed.

Validation passed 224 focused cases before the final lock correction, followed by
all 26 curriculum/benchmark cases after it (225 distinct cases overall). The one
unchanged long multi-act runner test remained deselected; the existing Gymnasium
fixed-bound warning remains. The independent reviewer passed eight selected checks
and separately verified restored optional confirmations and a concurrent selection
lock conflict with zero held-out snapshot access. Review corrected native encounter
reporting and that lock race; no blockers remain. Compileall, Python 3.10 syntax
checks for 438 files, installed command usage and diff checks passed.

The final artifact audit verified all **1,728 combat episodes / 34,810 decisions**,
all 320 frozen snapshot digests, policy initialization chains, unchanged model/
vocabulary/objective, summary calculations, canonical zero rewards, task outcomes
and 2,102 owner-only private files. The four hybrid trajectories also passed the
existing canonical loader. Evidence is entirely headless; no native bridge build
or live-policy capability is claimed. At this milestone boundary, full-run data
and selector behavior remained useful next work;
this result does not justify an unbounded combat parameter search.

## Milestone 6: full-run learning

Begin once the training pipeline is reliable and combat learning shows useful
progress, informed by the hybrid evaluations already running since milestone 3.
Reliable campaign victories and completion of all combat tuning are not entry
requirements. Keep the heuristic and frozen hybrid checkpoints as comparisons.

Train the shared model across every `full_run_v2` decision family using
`FullRunEnv`. Broaden the imitation corpus to rewards, shops, rests, map travel,
events and endings before online training. Expand the model's feature vocabulary
explicitly when required. Initialize from the combat encoder/policy where
compatible, and reinitialize or retrain its value head: combat return and full-run
return are different targets. Do not blend their transitions as one task.

The default full-run training reward remains +1 for actual Architect victory and
0 otherwise, with undiscounted episodic return. Add a `run_victory` component that
maps exactly to the canonical base reward and a separate full-run `RewardSpec`
preset with all combat weights zero. Combat shaping is optional and
separately identified; final selection/evaluation uses actual run victory. If
wins are too rare for a useful signal, use better public-information demonstrations
or a declared curriculum, including easier continuation starts where appropriate.
Evaluate from genuine run starts separately. Never expose future outcomes or a
real hidden draw order to a demonstrator/planner acting as a public policy.

Start with Overgrowth A0, then include Underdocks. Other characters and higher
ascensions follow measured Ironclad progress. Shared public schemas do not alone
guarantee model transfer to live producer details: native card previews and
headless descriptors need feature-level compatibility checks before deployment.

**Acceptance:** every current decision family reaches the learned policy through
the existing legal-candidate interface; real defeat, victory and cutoff semantics
remain intact. Produce held-out full-run win-rate and compute-budget comparisons
for heuristic, hybrid and fully learned policies. Do not label boosted fixtures
or assisted continuations as normal-HP agent victories.

### Milestone 6 usage and implementation choices

The shared PPO update/GAE code now collects either combat episodes or full
campaigns through the existing `FullRunEnv`. Full-run data uses canonical
trajectories directly, without combat sidecars. `sts_full_run_reward_v1` measures
only `run_victory`: +1 at the engine-owned Architect ending, zero on every other
transition. Its resolved preset declares every combat weight zero. Gamma must
be 1. The later [configurable v2 objective](#configurable-full-run-rewards) adds
combat shaping without changing v1 artifacts or canonical demonstrations. Existing
combat-v1 reward serialization and inference loading are preserved exactly;
cross-task resume, combat sidecars and hybrid initialization reject run objectives.

Collect separate training and development data, then transfer a selected combat
checkpoint explicitly. Replace `COMBAT_MODEL` with its `.sts-model` path:

```bash
sts-agent-train collect-run --output-dir runs/run-train --cases 4 \
  --include-fixtures --max-decisions 1536 --time-limit 300
sts-agent-train collect-run --output-dir runs/run-validation --cases 2 \
  --split validation --max-decisions 1024 --time-limit 120
sts-agent-train imitate --full-run --initialize-combat COMBAT_MODEL \
  --train-dir runs/run-train --validation-dir runs/run-validation \
  --output-dir runs/run-imitation --updates 256 --learning-rate .0003
sts-agent-train ppo --checkpoint runs/run-imitation/final.sts-model \
  --config configs/training/full_run_ppo_overgrowth.json \
  --output-dir runs/run-ppo-overgrowth --decisions 1024 --time-limit 600
sts-agent-train ppo --checkpoint runs/run-ppo-overgrowth/final.sts-model \
  --config configs/training/full_run_ppo.json --start-index 2000 \
  --output-dir runs/run-ppo-mixed --decisions 1024 --time-limit 600
```

The optional fixtures author rewards, shops, rests, events, treasure and relic
choices on a valid campaign map, with 40 HP/1,000 gold and a 32-decision cap.
One separate assisted campaign starts with 10,000 HP and five upgraded Byrd
Swoops to reach later acts and the ending through legal actions. The teacher
receives only public decisions. These records have `controlled_fixture` evidence;
they teach imitation actions but provide **no normal-run value labels**, including
on victory. Genuine starts and their outcomes remain separately counted.
Cutoff demonstrations also have no Monte Carlo value target. Review the recorded
context/ending coverage before starting PPO; a time limit can stop demonstrations
before their intended endpoint.

Vocabulary expansion unions the old vocabulary with training-only public names.
The transfer remaps embeddings by name, including unknown row zero, and copies
compatible shared/actor weights. The critic gets a fresh hidden layer and zero
output; Adam, learner RNG and sampling cursor start fresh. The imitation report
records this lineage. Validation/test names never expand the vocabulary.
Exact same-task resume still uses the public bundle plus its owner-only matching
resume file and requires unchanged implementation/runtime/configuration.

The two PPO configurations start with Overgrowth, then include Underdocks. A
changed region population is an explicit new experiment: carry inference weights
and vocabulary, use a fresh optimizer and distinct/continued training cursor.
The examples above reserve a later training cursor for the second stage. Both
configs cap batches at 512 decisions and episodes at 1,024; the remaining batch
quota can close an episode earlier. Such cutoffs retain the final ready public
observation for bootstrapping, while true victory, defeat and abandonment have
zero bootstrap. Timeouts before dispatch create no invented transition. These
bounded pilots do not guarantee enough late-run reward signal for strategic
improvement.

Play or compare the frozen full-run checkpoint:

```bash
sts-agent-play --checkpoint runs/run-ppo-mixed/final.sts-model \
  --output-dir runs/run-playback --max-decisions 1024 --time-limit 120
sts-agent-evaluate --full-run --checkpoint runs/run-ppo-mixed/final.sts-model \
  --combat-checkpoint COMBAT_MODEL --output-dir runs/run-test --split test \
  --campaign-cases 8 --max-decisions 1024 --time-limit 120
```

The full-run actor scores every headless decision family through legal candidates,
including nested selectors and reward presentations. The combat-only comparison
still uses authoritative combat ownership for hybrid routing. All three evaluation
policies start from identical genuine Ironclad A0 campaigns with the same
Gym-derived engine seed per case; separate interleaved train/development/test
roots keep their source populations separate. A public plan pins policy/source
identities, limits, cases and paired groups before the first action. Private
seeds stay in owner-only replay files. Reports retain all planned cases, including
failures and unattempted rows; incomplete comparisons cannot claim improvement.
Win rates, conservative grouped uncertainty, decisions and compute time are
reported for each policy. This bounded comparison fixes its checkpoint before
test; it is not a new adaptive checkpoint-selection system.

### Milestone 6 measured results

The 2026-09-29 pilot is retained under
`runs/full-run-milestone6-20260929/`. Its protocol fixed the corpus, 256 imitation
updates, 1,024 Overgrowth PPO decisions followed by 1,024 mixed-region decisions,
and the final-checkpoint comparison before training. Development feedback did
not select or tune the tested checkpoint.

Training demonstrations contain 1,665 decisions: four genuine campaigns ended
in defeat after 437 decisions; six authored room continuations supplied 192
decisions before their caps; the assisted campaign supplied 1,036 decisions and
completed the Architect ending. All ten current headless decision contexts were
present. The assisted 1,228 decisions supplied no value labels. Two separate
ordinary development demonstrations supplied 411 decisions and both ended in
defeat. Only the 437 ordinary training decisions supplied critic targets, all zero.

Transfer retained the combat checkpoint's 156 vocabulary names and added 818
names from training records, yielding 974. Teacher agreement rose from 28.95%
to 77.78% on training data and from 48.66% to 77.86% on the separate development
data. This is imitation agreement, not a game win rate. The warm-up took 419.57
seconds; 172.22 seconds were training-corpus encoding and 3.53 seconds were
optimizer updates. The packed training corpus occupied 1,081,776,955 bytes.
Loading, validating and encoding public histories dominate this small CPU model's
cost; these are measured workflow timings, not a dedicated hardware benchmark.

Each PPO stage recorded 11 ordinary-start attempts: nine defeats and two quota
cutoffs, with no failed episodes or victories. The stages took 136.58 and 127.14
seconds including collection/checkpoint/report work, with roughly 783 MB and
762 MB peak process RSS respectively. Four complete collection/update batches
trained all 2,048 requested decisions. Every return and advantage was zero, so
the policy changes came from entropy regularization; the policy-gradient and
value losses remained zero. This validates full-run collection/update/resume,
but does **not** demonstrate successful learning from run-victory reward.

The fixed final inference bundle is
`runs/full-run-milestone6-20260929/ppo-mixed/final.sts-model`, SHA-256
`afc6d63bd5a3be70c8d8243e689e3764db256f645a951f78e4de58aad1345248`.
Keep this pilot distinct from the selected milestone-5 combat policy. The two
development comparison cases produced no wins for any policy, and the fully
learned policy lost much earlier. A later continuation curriculum or better
public demonstrations must establish useful reward signal before longer
full-run training is justified; that is a separate experiment, not a reason
to retune this checkpoint on its held-out cases.

The held-out comparison used eight paired ordinary starts, four per first-act
region, with a 1,024-decision/120-second limit per episode:

| Policy | Run wins | Defeats | Cutoffs | Mean last observed floor | Decisions | Episode execution seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Heuristic | 0/8 | 8 | 0 | 10.13 | 1,016 | 71.95 |
| Frozen combat hybrid | 0/8 | 7 | 1 | 9.13 | 1,514 | 201.24 |
| Fully learned | 0/8 | 8 | 0 | 1.00 | 346 | 30.04 |

The fully learned policy died on floor 1 in **every** development and test case.
Its shorter execution time reflects earlier defeat, not better efficiency.
No evaluation episodes failed or were omitted. The hybrid timed out on floor
10 after 288 card selections and 287 deselections, without a confirmation. That
existing selector weakness remains unresolved by this milestone.

All primary win-rate differences are zero; the conservative paired 95% bounds
are ±96.03 percentage points, so the small pilot establishes neither improved
win rate nor equivalence. The observed progression is plainly worse for the
fully learned checkpoint. Higher teacher agreement did not translate into
useful autonomous play. This experiment does not isolate whether imitation,
entropy-only PPO updates, or both caused the degradation.

Episode execution timings include simulation, projection, policy and recording;
they exclude later canonical-file validation. The whole held-out command took
353.05 seconds. The complete declared pilot, including corpus collection,
preparation, learning and both comparisons, took 1,433.96 seconds (23.90 minutes).
The [retained evidence](evidence/full_run_training_2026_09_29.json) binds the
protocol, reports, model hashes, runtime, outcome rows and available timings.
Source build is `4a13646269563ca3625af45aa8ac7a5fa2e5d928347f552da60211e3bdbe67b4`;
game-rule and heuristic identities are unchanged from milestone 5.

Validation passed 223 distinct focused checks across incremental runs, including
all-family learned scoring, actual Architect/defeat/abandonment semantics,
cutoff bootstrapping, task rejection, vocabulary remapping, exact CPU resume,
worker loading and paired evaluation. One unchanged long multi-act runner test
was excluded; milestone 7 retains the broad integration gate. Project-environment
`compileall game tests` passed. The independent review found and verified the
room-continuation correction, then passed eight focused checks in 16.86 seconds
and six installed CLI integration/no-clobber checks in 10.076 seconds. Those
disposable checks are implementation evidence, not gameplay-strength evidence.
The final artifact audit verified 65 complete trajectories and 7,737 actions,
reloaded all 22 PPO episodes through the canonical loader, and matched all 401
recorded learned-policy evaluation choices by replaying the frozen checkpoint.
The poor choices are reproducible: for example, it ended its first three turns
in one development fight with all three energy unspent. Ten inference bundles
retain their source/objective identities; 78 private artifact files passed
permission checks, and no pilot partials remain. No live bridge work or
milestone-7 broad integration/clean-package gate was performed.

### Training-time benchmark (2026-09-29)

This baseline precedes the [performance optimization](#training-performance-optimization-2026-09-29)
reported below; retain these original measurements for comparison.

The dedicated timing experiment uses the unchanged milestone-6 source and final
full-run checkpoint on local macOS 26.6.2 / arm64, Python 3.11.15 and PyTorch
2.13.0. Each worker has one PyTorch CPU thread and one synchronous collector.
The host reports 18 logical CPUs; its hardware model was unavailable under the
sandbox. These are elapsed wall times, with no cold-file-cache claim.

Three fresh workers start from identical model weights, learner RNG and training
roots, each collecting 512 decisions with the current mixed-region PPO config.
Canonical recording, rollout reports, two PPO epochs (64 optimizer steps), and
three public/private checkpoint publications remain enabled. Replicas do not
continue training one another. All three have the same actions, masks,
likelihoods, targets and final model weights.

| PPO measurement | Seconds |
| --- | ---: |
| Complete process, median | 64.43 |
| Complete process, minimum–maximum | 64.06–64.87 |
| Collection, median | 62.04 |
| Model update, median | 1.18 |
| Three checkpoint publications, median | 0.051 |

Whole-process throughput is **7.95 decisions/second**. Collection accounts for
about 96% of elapsed time, whereas optimizer work is under 2%. Peak process RSS
is approximately 570–584 MB. Each replica has seven defeats and one quota cutoff,
with no failures or positive run reward. This measures the current policy's
workload, not successful learning or time to a competent agent.

One complete imitation repeat uses the existing 1,665 training decisions and 411
separate development decisions, the same combat-to-run transfer recipe, and 256
updates at batch size eight. It takes **421.00 seconds (7.02 minutes)** including
process startup. Data preparation takes **412.58 seconds**, broken down below
using exclusive timers so nested operations are counted once.

| Imitation preparation | Seconds |
| --- | ---: |
| Canonical loading and validation | 163.10 |
| Observation feature encoding | 197.01 |
| Vocabulary fitting, excluding canonical loading | 52.18 |
| Other preparation | 0.29 |

The actual 256 optimizer updates take **3.34 seconds**; four before/after corpus
evaluations take 3.96 seconds and checkpoint publication takes 0.034 seconds.
The packed training corpus occupies 1.082 GB; peak process RSS is 2.974 GB.
The current recipe decodes every training trajectory three times (manifest
checking, vocabulary fitting and encoding) and every development trajectory
twice. This repeat confirms the earlier pilot's data-preparation bottleneck.

The separate 128-decision profile matches the baseline's actions, likelihoods
and values. Of its 46.43 seconds of profiled collection, the public `from_dict`
path accounts for 36.01 cumulative seconds; `get_type_hints` is called 1,292,349
times and accounts for 18.69 cumulative seconds. These nested times overlap and
include profiler overhead. By comparison, model forward calls total 0.109
seconds and engine `apply` calls total 0.155 seconds in that profile. Repeated
public conversion/type resolution is the first optimization target suggested
by this measurement; the profile is not a throughput benchmark.

At this measured PPO workload, 10,000 decisions project to about 21 minutes,
100,000 to 3.50 hours, and one million to 34.96 hours. These are linear throughput
projections, not additional completed experiments. Longer campaigns accumulate
larger observations and can cost more per decision. The earlier complete
milestone-6 pilot took 23.90 minutes including demonstration collection and
evaluation; that figure is historical workflow timing, not a repeated benchmark.

Results and artifact bindings are retained in
[the benchmark evidence](evidence/training_time_benchmark_2026_09_29.json), with
raw reports and the one-shot script under
`runs/training-time-benchmark-20260929/`. To repeat the protocol, prepare a fresh
owner-only private directory containing a mode-0600 copy of the original
`runs/training-time-benchmark-20260929-private/seeds.json`, then run:

```bash
PYTHONPATH=. .venv/bin/python runs/training-time-benchmark-20260929/benchmark.py \
  --output-dir runs/training-time-repeat \
  --private-dir runs/training-time-repeat-private
```

Use fresh output and private directories; existing artifacts are not overwritten.
The script includes a separate 128-decision collection profile, excluded from
throughput statistics. No game/training implementation or accepted checkpoint
was changed, and no held-out test cases were used. The next performance task is
to reduce repeated public-observation conversion and validation, and reuse
prepared corpus features, while preserving boundary checks and exact action
mapping. No optimization is implemented by this benchmark.

The five benchmark workers completed in 662.96 seconds (11.05 minutes).
Post-run validation reloaded all 27 new canonical trajectories (1,664 actions)
in 20.17 seconds, verified identical public states/actions across the PPO
replicas, checked 42 private files' permissions, and confirmed unchanged source
and input identities with no partial artifacts. No gameplay suite or release
gate was needed for this measurement-only change.

### Training performance optimization (2026-09-29)

The first three measured passes reduced data-processing overhead while preserving
public observations, action mappings and numerical training results. The earlier
passes added bounded static schema-metadata caching, cheaper exact primitive
handling, and removal of redundant encoding validations. Their original
[source and timing evidence](evidence/training_optimization_2026_09_29.json) and
[second-pass evidence](evidence/training_optimization2_2026_09_29.json) remain
unchanged. The third pass reuses work within one observation or corpus preparation.

For standard combat and full-run PPO environments, a training-only encoder keeps
the freshly validated packed graph for the exact current decision object. Gym
padding and learned features share that graph; returned Gym arrays remain
independent copies. The retained pair is cleared before every encoding attempt
and when collection closes, including failures. Different decision objects cannot
reuse it. Custom environments, encoder subclasses and non-default capacities keep
the original independent encoding path. Standalone encoders still validate every
input; no arbitrary caller-supplied graph becomes a trusted feature input.

Full-run imitation opts into `corpus_paths(..., retain=True)`, which returns a
one-use handoff of the trajectories already validated against the manifest. The
loader reuses those snapshots for vocabulary fitting and feature preparation,
rechecks split, duplicate, task and reward constraints, and releases each decoded
episode as its examples are built. Retained snapshots refer to the bytes just
validated; later disk replacement cannot change them. A consumed handoff rejects
reuse. Ordinary path inputs still read and validate current files, once per
preparation. The default `corpus_paths()` result remains a list of paths. There
is no global or persistent disk cache.

The unchanged benchmark script, models, corpus, seeds and configuration were run
in fresh output directories on the same CPU with one PyTorch thread:

| Measurement | Original baseline | Second pass | Third pass |
| --- | ---: | ---: | ---: |
| Complete 512-decision PPO process, median of three | 64.43 s | 23.40 s | **19.24 s** |
| PPO decisions per second | 7.95 | 21.88 | **26.61** |
| PPO collection, median | 62.04 s | 21.06 s | 16.89 s |
| PPO model update, median | 1.18 s | 1.16 s | 1.16 s |
| Complete imitation process, one pass | 421.00 s | 124.35 s | **89.18 s** |
| Imitation data preparation | 412.58 s | 115.83 s | 80.47 s |
| Feature encoding within imitation preparation | 197.01 s | 41.97 s | 42.93 s |

The latest pass adds **21.6% PPO throughput**, with repeats spanning
19.21–19.26 seconds, and makes the imitation recipe **1.39× faster**. Across all
three passes, PPO is **3.35× faster** and imitation **4.72× faster** than the
original benchmark. Canonical trajectory loads fall from 37 to 13: once for
each of the 11 training and two validation files. Their loading/validation time
falls from 55.49 to 19.43 seconds. Vocabulary work takes 17.96 seconds and the
256 optimizer updates take 3.52 seconds. Feature extraction itself is unchanged.

In the separate 128-decision profile, graph packing drops from 260 to 131 calls
and full-run public parsing from 653 to 524 calls. Profiled timings include
instrumentation overhead and are excluded from throughput figures. Observation
processing and corpus preparation still dominate optimizer time.

Retention trades some memory for fewer parses. Peak imitation process RSS rose
from **3.002 to 3.155 GB** (5.1%); the packed training corpus remains 1.082 GB.
A separate fresh-process comparison of direct path loading with a frozen
vocabulary matched all labels, references and arrays for all 1,665 training
examples. Preparation took 53.96 seconds before and 54.31 seconds after, with peak
RSS rising from 2.239 to 2.359 GB. That path already loaded each file once when
using a frozen vocabulary; it has no measured speed benefit here. During
vocabulary fitting, all decoded trajectories are held together, so larger
corpora can require more memory than the prior streaming passes. These direct
loader checks are separate from the full training benchmark.

Validation passed **650 agent/package tests** in 290.93 seconds, the 14 new
focused regressions in 2.34 seconds, and compilation of `game` and `tests`.
The comparison against saved previous source matched 891 arrays, wire bytes and
reference mappings across all ten full-run contexts, a late-campaign state and
ten legacy examples in 3.76 seconds. Independent semantic review accepted the
change after checking custom-capacity fallback, identical rollout updates,
corpus equivalence, split/reuse rejection and file replacement behavior; its
independent probe took 0.983 seconds.

The final audit reloaded 27 canonical trajectories containing 1,664 actions.
Every public state/action and PPO training record, all 256 imitation numerical
update metrics and evaluations, and all 14 model weight sets match the previous
optimization exactly. Private permissions and incomplete-artifact checks passed.
Game rules, public schemas, objectives and model architecture are unchanged.
Inference bundles remain usable; exact training resumes retain the source-build
requirement. Historical checkpoints and evidence were preserved.

At this workload, 100,000 PPO decisions project to **1.04 hours** and one million
to **10.44 hours**, excluding extra evaluation. Longer campaigns can cost more per
decision. Three PPO replicas and one imitation pass provide timing evidence, with
uncontrolled OS file caches and background load. All PPO victory rewards remain
zero; these optimizations leave the measured playing behavior unchanged.

The [latest optimization evidence](evidence/training_optimization3_2026_09_29.json)
binds the source identities, inputs, validation and output artifacts. Raw results
are under `runs/training-optimization3-20260929/benchmark/`; the unchanged script
and fresh-directory procedure above reproduce the protocol. Benchmark execution
took 159.22 seconds (2.65 minutes), and the final artifact audit took 8.90 seconds.

### Parallel PPO collection (2026-09-29)

The `ppo` command supports `--workers 1` through `--workers 8` for both combat and
full-run tasks. The default remains one local collector, preserving the existing
serial sampling path. For example:

```bash
sts-agent-train ppo --checkpoint runs/run-imitation/final.sts-model \
  --config configs/training/full_run_ppo.json --output-dir runs/run-ppo-parallel \
  --workers 4 --decisions 2048 --time-limit 600
```

With multiple workers, the parent owns Adam and the update RNG. Spawned processes
each use one Torch thread and perform simulation, public encoding, inference and
recording locally. They persist between rounds and receive a copied snapshot of
the same behavior policy for each round. Completed public feature batches return
through pipes; transfer threads leave the parent responsive to cancellation and
deadlines. The parent merges batches by worker index and then performs the PPO
update. A worker failure discards the round and closes the entire pool, with no
retry or update from a successful subset. Completed recordings remain available;
interrupted recordings remain `.partial`.
On interruption, progress counts include only workers that returned a result;
other workers may have left recordings that are absent from the stopped report.

`rollout_steps` and `--decisions` remain **total** budgets. A 512-decision rollout
with four workers gives each worker 128 decisions, not 512. The last local episode
closes at that quota and bootstraps its actual final observation; GAE never crosses
a worker's episode boundary. Smaller per-worker horizons can reduce the chance
of observing a full-run victory, so choose a larger total rollout when longer
campaigns need to finish. Throughput alone does not establish learning quality.

The parent draws worker action seeds in stable index order from its private action
generator. Each worker reserves a disjoint range of episode indexes as large as
its decision quota. The next committed cursor skips the whole reserved range,
including unused indexes. Region/encounter selection uses a separate schedule:
`iteration * active_workers + worker_index`, advancing by `active_workers` for
each local episode. This avoids seed-range strides repeatedly selecting the same
region. Seeds and cursors remain private and never become policy inputs or public
progress fields. Results are independent of worker completion order when time
limits do not interrupt collection.

Worker count is an execution option rather than a new field in existing PPO JSON
configs or inference manifests. Existing inference bundles still load. Exact
resume requires the saved worker count, allocation schedule, source, runtime and
rollout boundaries. Worker RNGs and games are recreated each round, so idle
processes hold no additional resume state. Python callers should use
`with PPOLearner(..., workers=4) as learner:` or call `close()`; executable scripts
using spawn need the usual `if __name__ == '__main__':` entry-point guard.

The fixed-budget benchmark used the same initial model, mixed-region config and
private starting plan for three fresh invocations of each worker count, on the
same 18-logical-CPU arm64 host. Every invocation trained 1,024 decisions in two
512-decision rounds, including recording, optimization and checkpoints. Workers
were reused for round two. The table reports medians; complete invocation times
also include Python startup and pool cleanup.

| Workers | Complete 1,024-decision invocation | First collection, 512 decisions | Warm collection, 512 decisions | Invocation speedup |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 37.37 s | 16.69 s | 17.15 s | 1.00× |
| 2 | 21.45 s | 9.03 s | 8.81 s | 1.74× |
| 4 | 14.09 s | 5.51 s | 4.86 s | 2.65× |
| 8 | 10.40 s | 3.86 s | 2.73 s | 3.59× |

Four workers reached **72.67 decisions/s** and eight reached **98.48 decisions/s**,
including invocation overhead. Updates stayed around 1.13–1.17 seconds each.
Within each worker setting, all three replicas produced identical numerical
rollouts and final weights. Across settings, game samples and local cutoffs differ,
so the main table compares a fixed decision budget, not identical trajectories.
An additional comparison executed the four-worker first-round jobs sequentially:
it took **17.13 seconds** versus the parallel median of **5.51 seconds**. All 512
public states/actions, masks, likelihoods, values, rewards and GAE results matched.
That single reference timing confirms a collection speedup on identical game work.

Start with four workers when enabling parallelism; eight was fastest in this
measurement. More processes use additional memory, and total pool RSS was not
measured. The default remains one worker to preserve existing experiments.
The first serial rollout and updated weights also match the previous optimization
exactly. All measured full-run victory rewards remained zero, and more workers
caused more quota cutoffs; this is throughput evidence, not improved playing strength.

The [parallelization evidence](evidence/training_parallelization_2026_09_29.json)
binds source, inputs, timings and validation. Raw results and reproduction scripts
are in `runs/training-parallel-20260929/`. The 12 benchmark invocations took
248.91 seconds. An artifact audit validated 231 canonical trajectories containing
12,288 actions, restored all 48 published checkpoint pairs, and checked permissions
on 298 private files. It took 52.18 seconds while the regression suite ran.
No partial benchmark artifacts or reused training reset seeds were found.
The independent semantic review took 272 seconds and found no blocking issue.
Final validation passed **665 agent/package tests in 322.42 seconds**, with the
same three Gymnasium observation-space warnings as before, and compilation of
`game` and `tests`. Focused tests exercise real spawned workers, exact resume,
frozen probabilities, seed/scenario coverage, worker crashes, blocked pipe sends,
spawn interruption, forced cancellation/deadlines and installed CLI SIGTERM.
Game rules, public observations, reward objectives and model architecture are
unchanged. Inference compatibility is retained; historical evidence was preserved.

## Milestone 7: usable commands and final delivery checks

The installed `sts-agent-train`, `sts-agent-evaluate` and checkpoint playback
commands were added incrementally through milestones 1–6. This milestone verifies
their delivery from a built wheel in fresh environments, including configuration
errors, finite execution, exact resume, reports and worker propagation. The default
heuristic path and canonical recording semantics remain unchanged.

Two delivery fixes were needed. Checkpoint playback now reports the missing
`sts-agent[train]` extra as a structured failure instead of a Python traceback.
Malformed curriculum JSON now receives a parser error before any output is
created; partial nested PPO settings still use their existing defaults. Unexpected
import failures continue to propagate, so optional-dependency guidance cannot
hide unrelated defects.

Install `'.[train]'` for training and checkpoint commands, or `'.[dev,train]'`
to include the Python test suite. Core installation has no runtime dependencies;
ordinary heuristic playback and every command's help work without NumPy, Gymnasium
or Torch. The installed commands use the canonical `game` package.

| Workflow | Main report | Delivery checks |
| --- | --- | --- |
| `sts-agent-train collect` / `collect-run` | `demonstrations.json` / `run-demonstrations.json` | Separate training/validation corpora; finite episodes; declared assisted fixtures |
| `sts-agent-train imitate`, with optional `--full-run` | `imitation.json` | Initial/final bundles, combat actor transfer, exact resume with matching private state |
| `sts-agent-train ppo` | `ppo.json` | Complete-update checkpoints, total decision/time budgets, 1–8 collectors, saved worker count on resume |
| `sts-agent-train curriculum` | `curriculum.json` | Three distinct learners through five finite stages; stage collection remains serial |
| `sts-agent-evaluate` | `baseline.json`, `hybrid.json`, `full-run.json` or `benchmark.json` | Paired policies, frozen populations, development selection and locked held-out evaluation |
| `sts-agent-play --combat-checkpoint` / `--checkpoint` | Command summary and canonical trajectories | Correct task routing, two-worker playback and explicit task-mismatch errors |

Use a fresh output directory per invocation. Public inference bundles and reports
are separate from owner-only resume files and replay audits. Exact resume requires
matching implementation sources, runtime, corpus/objective and worker allocation.
These remain deliberate compatibility checks; this milestone adds no migration
of historical optimizer/RNG state.

The clean-install smoke used Python 3.11.15 on macOS arm64, Torch 2.13.0,
NumPy 2.4.6 and Gymnasium 1.0.0. Both fresh virtual environments disabled system
site packages, installed offline from exact cached dependency wheels and passed
`pip check`. Commands ran from a neutral directory with `PYTHONPATH` removed;
their imports came from the installed wheel. The core and training installations
took 1.61 and 9.38 seconds respectively. This is the tested platform and dependency
combination, not an executed cross-platform or Python 3.10 matrix.

All **48 installed-command smoke checks passed in 69.03 seconds**. Combat and
full-run imitation, plus two-worker PPO for both tasks, matched uninterrupted
training exactly after resume: model tensors, optimizer state, RNG and cursors.
Inference ZIP timestamps can differ even when these learning states match.
A separate installed two-worker SIGTERM check returned exit 130, removed its
process group and restored its last complete checkpoint; the check took 2.94 seconds.

The artifact audit validated **222 canonical trajectories with 539 actions**,
**190 combat sidecars**, all **77 inference/private checkpoint pairs**, and
permissions on **332 private files** in 6.02 seconds. It found no partial artifacts
in the completed smoke outputs and verified every packaged game source against
the checkout. The tiny decision limits, including a separate disposable frozen
benchmark, establish integration only and add no playing-strength evidence.

The two fixes passed 33 focused tests in 22.38 seconds and an independent semantic
review in 188 seconds. Final validation compiled `game` and `tests` and accounted
for all **8,447 collected tests**. The first broad invocation reported 5,063 passes
and one localhost-permission failure before its 20-minute command limit. The
remaining 3,383 tests passed in 361.98 seconds; the continuation starts at the
first unreported case, with the completed prefix retained. The synthetic socket
fixture passed separately in 0.01 seconds with loopback permission. It never
contacted a live bridge, and no source fix was needed. No code failures remain.

The [delivery evidence](evidence/training_delivery_2026_09_29.json) binds the
tested wheel, source identity, dependency versions, validation logs and a manifest
of 1,051 retained artifacts in `runs/training-milestone7-20260929/` and its separate
cancellation outputs. Temporary installation environments were removed after
validation. Initial investigation, implementation, packaging and review overlapped
over 475 seconds before the final gates; separate implementation time was not
measured. These headless checks required no native build or live game launch.

## Staged learning diagnostic (2026-09-29)

The follow-up comparison is complete. Its largest observed regression occurs
during PPO, with a separate non-combat selection failure already present before
PPO. This is a diagnosis of one retained checkpoint lineage on four fresh
development cases; it does not establish population playing strength.

The protocol froze five retained checkpoints, four validation cases (two genuine
Ironclad A0 starts in each first-act region), eight controller configurations and
the probe before execution. Each controller received the same campaign seed and
region within a case. Hybrids used the runner's authoritative combat ownership;
learned policies received only public decisions. Limits were 1,024 decisions and
90 seconds per episode, with a 30-minute total cap. No training, checkpoint
selection, held-out evaluation, objective change or native game access occurred.

All **32 episodes** completed their declared execution, recording **9,350
decisions** in **507.45 seconds**. There were 26 defeats, six decision-budget
cutoffs and no wins, failures, time cutoffs or omitted pairs. The heuristic's
mean last observed floor was 11.00. The table includes floor-zero cutoffs in its
means; these figures are descriptive progress measures, not victory estimates.

| Frozen actor | Mean floor: learned combat, heuristic elsewhere | Mean floor: learned at every decision | Full-policy cutoffs |
| --- | ---: | ---: | ---: |
| Original combat checkpoint | 11.25 | Not evaluated | — |
| Transferred actor, before imitation | 11.00 | 1.75 | 3/4 |
| Full-run imitation | 10.75 | 2.75 | 3/4 |
| Final mixed-region PPO | 1.25 | 1.50 | 0/4 |

All six cutoffs occurred on floor zero in a relic card selector. Their final
32 actions alternated between selecting and deselecting a card; confirmation was
legal after selection. The initial actor transfer and 256-update full-run imitation
therefore did not reliably complete this interaction under greedy playback.
Ending the loop is a distinct requirement from improving combat.

The fixed common-state panel used the first 64 combat-context and 16 other
decisions from each heuristic campaign: **320 public decisions** scored by all
five checkpoints. It includes the intermediate Overgrowth PPO checkpoint, which
was not a separate campaign controller. These groups describe public context
labels; hybrid routing also handles nested combat ownership. Teacher agreement
measures behavior on the teacher's states and is not a gameplay score.

| Stage | Teacher agreement on 256 combat states | End turn with energy and a legal card play, out of 193 opportunities |
| --- | ---: | ---: |
| Original combat | 122/256 | 0/193 |
| Transferred actor | 120/256 | 2/193 |
| Full-run imitation | 209/256 | 0/193 |
| Overgrowth PPO | 182/256 | 0/193 |
| Final mixed-region PPO | 60/256 | 22/193 |

Imitation and Overgrowth PPO chose the same action on 225/256 combat states;
imitation and final PPO agreed on only 60/256. On those same states, mean action
entropy rose from 0.8661 after imitation to 1.2206 after Overgrowth PPO and 1.5399
after mixed-region PPO. This locates the largest sampled behavior change between
the two saved PPO stages. It does not isolate changing regions as the cause:
region mixture and additional optimizer updates changed together. The end-turn
measure is a warning sign, not proof that every available card was useful.

The transfer itself copied all **29 shared/actor tensors**, the unknown embedding
and all **156 existing token embeddings** exactly. Expanding the vocabulary to
974 names added 818 randomly initialized embeddings, which can change inputs
even when shared weights are preserved. The transferred actor changed 13/256
combat choices and 16/320 overall choices relative to the source. A separately
identified shadow actor replaced only the new embeddings with the original
unknown embedding. It reproduced all 320 original choices and every probability
exactly. This isolates the vocabulary contribution on the fixed panel; it does
not measure its causal effect on campaign outcomes. The shadow was never trained,
published as a deployable checkpoint or used for campaign decisions.

The saved PPO audit covers all **2,048 training decisions in four batches**.
Every recorded reward, advantage, return, value and next value was exactly zero.
Both policy loss and value MSE were zero throughout the reported updates; total
loss matched the entropy term within 3.1e-10. The fresh PPO optimizers still made
**160 optimizer steps**, driven by entropy regularization with weight 0.01.
The agent received no sampled victory signal directing those changes. All four
updates reached the KL stopping threshold, with final approximate KL values
0.31425, 0.06393, 0.19049 and 0.03666 against a target of 0.03. This check runs
after each epoch and does not roll back that epoch. The full-run critic remained
zero on the probe; the combat critic estimates a different objective and its
values are not compared as calibrated run-victory probabilities.

The [diagnostic evidence](evidence/training_stage_diagnostic_2026_09_29.json)
binds the protocol, checkpoint hashes, paired episode results, public trajectories,
private audit digests, probe, scripts and PPO source reports. The canonical loader
validated all 32 new trajectories, and their replay audits verified pairing and
owner-only permissions. Source and model bytes remained unchanged. Analysis and
validation took 104.67 seconds; independent read-only reviews checked campaign
routing, the shadow control, metric denominators and the zero-signal attribution.
Raw artifacts are retained in `runs/training-stage-diagnostic-20260929/` with
separate private replay data. No production behavior changed in this experiment.

## Configurable full-run rewards

Full-run PPO now accepts `sts_full_run_reward_v2`. Set the finite weights in
`training.reward.weights` inside the existing PPO experiment configuration.
All supported components are measured even when their weights are zero. Unknown
names and malformed values reject before training. The historical v1 objective
and checkpoint identities remain unchanged and loadable for inference.

| Component | Measurement on one reconciled action | Example weight |
| --- | --- | ---: |
| `run_victory` | 1 at actual run victory | 1.0 |
| `run_defeat` | 1 at actual run defeat, including lethal events | -1.0 |
| `run_abandoned` | 1 at explicit abandonment, distinct from defeat | -1.0 |
| `combat_win` | 1 when a newly completed fight reports victory | 0.1 |
| `combat_loss` | 1 when a newly completed fight reports defeat | 0.0 |
| `win_hp_fraction` | HP / max HP after victory cleanup and automatic healing; 0 otherwise | 0.025 |
| `end_turn_action` | 1 on the accepted `end_turn` command | -0.001 |
| `potion_use_action` | 1 on accepted manual potion use, including outside combat | 0.0 |

These example weights are in
[`full_run_shaped_ppo.json`](../configs/training/full_run_shaped_ppo.json).
They are an editable starting configuration, not tuned performance results.
Omitted weights default to zero except `run_victory`, which defaults to 1.
Components add together: setting both `combat_loss` and `run_defeat` to -1
gives -2 for a fatal fight. The example assigns its terminal penalty through
`run_defeat` and leaves `combat_loss` at zero.

For example, winning a fight at 46/80 HP pays `0.1 + 0.025 × 46/80 = 0.114375`.
The campaign continues; reward collection does not pay for the same fight again.
Nested card/potion confirmations do not repeat the potion-use component, and
automatic revival does not count as manual potion use. Fights that finish during
room entry also report their confirmed result. Decision/time cutoffs are not
defeats; an executed combat win can still earn reward on the same step as a
nonterminal cutoff. Invalid, stale, uncertain and action-free cutoff attempts
produce no training reward measurement.

Start a new shaped experiment from a full-run imitation checkpoint with an
explicit objective reset and adoption of the preset's single-card policy:

```bash
sts-agent-train ppo \
  --checkpoint runs/full-run-milestone6-20260929/imitation/final.sts-model \
  --config configs/training/full_run_shaped_ppo.json \
  --reset-objective --reset-action-policy \
  --output-dir runs/full-run-shaped --decisions 512 --time-limit 300 --workers 2
```

`--reset-objective` requires different full-run objectives. It copies the actor
and frozen vocabulary exactly, initializes a fresh value head with zero output,
and starts fresh optimizer/RNG/counters. It records both objectives and the source
checkpoint in `ppo.json`. The critic now predicts the configured shaped return,
which is not a calibrated run-victory probability. The original checkpoint is
preserved. Direct combat-to-run transfer still goes through the existing full-run
imitation command.

The preset also enables the [shared policy-action layer](#shared-policy-actions-and-selection-order).
For subsequent training with the same objective and action policy, omit both reset flags.
Exact resume additionally supplies the matching `--resume-state`; changing
weights or resetting the objective during resume rejects. As before, historical
private optimizer states require their exact implementation/runtime to resume;
compatible inference weights can initialize a new experiment. Worker allocation
and total decision-budget semantics are unchanged.

`FullRunTrainingEnv` wraps the existing campaign environment for v2 PPO only.
It uses the adapter's allowlisted combat result and post-hook HUD measurements.
Structured policy observations and game rules are unchanged. Each shaped PPO
batch publishes `sts_ppo_rollout_v2` for the unrestricted action policy, or
`sts_ppo_rollout_v3` for the filtered policy, retaining the resolved objective, weighted
reward, individual components, and before/after public combat summaries. Its
episode rows bind those actions to canonical trajectory hashes. Components can
be rescored explicitly with `RewardSpec.shaped_full_run(new_weights).evaluate(...)`;
that does not alter the recorded objective or the original artifacts.

Canonical trajectories and `FullRunEnv` keep their original +1/0 run-victory
reward. Full-run demonstration value labels also retain their original objective;
old records are not retroactively given missing combat measurements. Evaluation
and playback accept v2 full-run checkpoints. Evaluation still compares actual
genuine-start run victories and records the training objective separately from
the evaluation objective. Higher shaped return alone is not evidence of stronger
campaign performance.

Validation for this change passed all 692 agent/package-layout tests in 327.05
seconds, Python compilation, and an independent semantic review of reward
boundaries, public measurements and objective transfer (145 seconds). An installed
two-worker PPO smoke trained on 128 accepted decisions in 3.16 seconds: six combat
wins produced a shaped return of 0.702319 and 103 nonzero advantages, with zero
full-run victories. Both episodes ended at decision cutoffs. Installed evaluation
and playback also accepted the shaped checkpoint. The 0.52-second artifact audit
verified exact actor transfer, all reward/action joins, canonical trajectories,
checkpoint identity and private-file permissions. Raw reports and validation
output are retained in `runs/full-run-rewards-20260929/`. This verifies training
integration, not improved playing strength; a larger training experiment has not
been run for these weights.

## Shared policy actions and selection order

The shared [`action_policy.py`](../game/agent/action_policy.py) layer restricts
policy choices over the complete public decision. It does not change native
legality, the canonical adapter, candidate order or game rules. The current
`commit_decisions_v1` policy includes the unchanged `commit_card_selection_v1`
restrictions on undo in known deferred selectors:

- Combat manual selections, relic card selections, Meat Cleaver Cook and Sea Glass
  retain every unselected pick up to the maximum. Selected cards cannot be
  deselected; Sea Glass's selected `choose_relic_reward` actions count as undo.
- Confirmation stays a separate recorded and budgeted command, available whenever
  the minimum is satisfied. Optional zero-card confirmation remains available,
  and meeting the minimum does not force completion before the maximum.
- Every ordered final selection is reachable from a newly opened empty selector
  by choosing its members in that order and confirming. Picks are never sorted.
  Attached selections commit their inherited members too; native free-slot reuse
  still determines the order when an attachment already contains selection holes.
- Bounds, selected membership and the complete pick/undo/confirm action set must
  match a recognized selector. Immediate choices and unknown shapes stay unchanged.
  Cook cancellation and potion actions remain legal, so this prevents selection
  toggles rather than guaranteeing progress through every navigation action.

It also prevents repeated card-reward inspection loops in combat reward screens
(main and extra rewards) and event reward batches. The first opening can be
closed. Reopening a reward that was already closed, with only reward navigation
in between, masks `close_reward`; choosing, skipping, rerolling and sacrificing
remain separate legal decisions. Inspecting a different reward does not reset
this allowance, so the agent can inspect A, inspect B, then resolve either first.
An actual gameplay command, including a reroll or an inventory change, resets
inspection. A reroll can keep the modal open; closing it then reopening counts
as repeated inspection of the rerolled offers.

The rule uses only public reward references, offer/option structure and recorded
public action history. It requires the current opening and an earlier close of
the same reward since the last gameplay command. Missing history, unknown or
incomplete modal shapes, non-card rewards and close-only exits retain full legal
support. Native candidates and their order stay intact; only the policy mask
changes. No choice or confirmation is dispatched automatically. This bounds the
recognized inspection loops, not every possible navigation or gameplay cycle.

The Act 1 and shaped full-run presets enable this policy. It is versioned
separately: existing checkpoints keep their original behavior, and historical
recordings are not rewritten. All-legal, original singleton and card-selection-only policy identities
retain their existing serialization. An explicit policy reset transfers weights
to a new experiment; it cannot be combined with exact optimizer resume.

The original `commit_single_card_v1` policy remains supported unchanged. It
prevents a mandatory single-card select/deselect loop:

1. The public selector must explicitly require exactly one card, with integer
   `minimum == maximum == 1` and manual confirmation.
2. Exactly one card must be selected. The only legal candidates must be that
   card's deselect action and the matching confirmation.
3. The last recorded public action must have selected that exact card in the
   same action family. A fresh attachment to a preselected engine state without
   that history keeps its undo action.
4. The policy mask then permits only confirmation. Selecting and confirming
   remain two separate, recorded and budgeted engine steps. A one-step budget
   can stop after selection; no hidden confirmation runs after the cutoff.

That original policy recognizes combat/rest `select_card`, `deselect_card`,
`confirm_selection`, and relic `choose_relic_card`, `deselect_relic_card`,
`confirm_relic_selection`. This is a structural rule over public fields, including
cases whose bounds become one after eligibility is capped. Empty selectors,
optional selections, multiple-card choices, immediate choices and unknown shapes
retain their full legal support. The filter neither sorts cards nor confirms an
optional selector as soon as its minimum is met.

The same function supplies the mask to imitation features, PPO sampling and
updates, worker models, evaluation and checkpoint playback. The canonical graph
and trajectories still expose every legal candidate. Filtered PPO rollout v3
(v4 for the Act 1 objective) records both `legal_mask` and `policy_mask`; replay verifies the policy version,
the chosen action and its sampling support. A forced confirmation has probability
one, log probability zero and entropy zero. Imitation rejects demonstrations with
excluded actions rather than silently dropping or relabelling them.

Unrestricted checkpoints and configurations use `all_legal_v1`, retaining their original
serialization and identities. New filtered checkpoints use inference bundle v3
and bind the action-policy version to corpus, experiment, behavior and resume
identities. Exact resume cannot change that policy. To enable it:

- For new imitation, add `--action-policy commit_decisions_v1` to the existing
  `sts-agent-train imitate` command, including full-run imitation when applicable.
- For PPO, use experiment schema `sts_ppo_experiment_v2` with
  `training.action_policy` set to `commit_decisions_v1`. The shaped full-run
  example configuration already does this.
- When the source checkpoint has a different action policy, add
  `--reset-action-policy`. This starts a new experiment with copied model weights
  and fresh optimizer, RNG and episode cursor; the source checkpoint is preserved.
  Add `--reset-objective` as well only when changing the full-run reward objective,
  which also resets the critic. Omit either flag when its setting is unchanged.
- Combat curriculum stages inherit their initial checkpoint's action policy.
  Inference loads it from the checkpoint; there is no separate playback override.

### Inventory of current headless card selectors

This inventory covers the current headless catalog and command families. It is a
source audit with focused engine tests, not a new live-game equivalence claim.
Counts below describe card definitions, not every possible eligibility, upgrade
or power-stack state. The core selection implementation caps bounds to eligible
cards and sometimes resolves the only required set without opening a choice.

There are **40 direct card-selector definitions**: eight immediate choices and
32 definitions using explicit toggle/confirm selection.

| Family | Definitions and selection bounds |
| --- | --- |
| Immediate hand choice (5) | Base Armaments; upgraded True Grit; Brand; Burning Pact; Scavenge. Each choice applies immediately. Upgraded Armaments and base True Grit do not ask for this choice. |
| Immediate pile choice (3) | Headbutt, Wish, Hologram. Each resolves one pick immediately. |
| Other explicit cards (2) | Neow's Fury: 0–2, upgraded 0–3, capped by hand space. Dual Wield: exactly one eligible attack/power. |
| Colorless explicit cards (7) | Discovery and Splash: 0–1; Purity: 0–3, upgraded 0–5; Secret Technique, Secret Weapon, Seeker Strike and Thinking Ahead: one. |
| Silent explicit cards (7) | Acrobatics, Dagger Throw, Survivor, Hand Trick and Nightmare: one; Hidden Daggers: two; Prepared: one, upgraded two. |
| Regent explicit cards (9) | Begone, Cosmic Indifference, Decisions Decisions, Glimmer, Photon Cut and Heirloom Hammer: one; Charge: two; Guards: 0–all eligible; Quasar: 0–1. Glimmer and Photon Cut put one card on the draw pile per selection. |
| Necrobinder explicit cards (7) | Cleanse, Graveblast, Sculpting Strike, Seance, Snap and Transfigure: one; Dredge: up to three required picks, capped by remaining hand space and eligibility. |

Other sources use the same core toggle/confirm mechanism:

| Source | Definitions and bounds |
| --- | --- |
| Potions (9) | Ashwater: optional exhaust; Gambler's Brew: optional discard/redraw; Droplet of Precognition, Liquid Memories and Touch of Insanity: one; Attack, Skill, Power and Colorless Potions: 0–1 generated offer. |
| Powers (6) | Entropy, Stratagem, Tools of the Trade, Foregone Conclusion and Tyranny: required picks based on stacks, capped by eligibility; Well-Laid Plans: 0–stacks retained cards. |
| Combat relics (3) | Toolbox: 0–1 generated offer; Gambling Chip: 0–all discard/redraw; Choices Paradox: one generated offer. Crossbow resolves automatically and is not a selector. |
| Monster | Knowledge Demon: one curse offer. |

The **20 persistent relic pickup selectors** are defined in
[`pickup.py`](../game/headless/relics/pickup.py) and
[`ancient_pickups.py`](../game/headless/relics/ancient_pickups.py).
Bounds are capped by eligibility.

| Operation | Relics and requested counts |
| --- | --- |
| Clone | Dolly's Mirror: one. |
| Transform | New Leaf: one; Astrolabe: three, then upgrade the replacements. |
| Remove | Biiig Hug: four; Empty Cage: two; Precarious Shears: two, then damage; Precise Scissors: one; Preserved Fog: three, then add Folly. |
| Upgrade | Pomander: one; Yummy Cookie: four. |
| Enchant | Beautiful Bracelet: three; Electric Shrymp: one; Gnarled Hammer: 0–3; Kifuda: 0–3; Pael's Growth: one; Punch Dagger: one; Royal Stamp: one; Tri-Boomerang: three. |
| Replace/store | Claws: 0–6 attribute-preserving Maul replacements; Pael's Tooth: store five cards. |

Other card-choice surfaces have distinct command or completion rules:

| Surface | Current behavior |
| --- | --- |
| Sea Glass | Choose 0–15 generated offers, then confirm. Both selection and deselection use `choose_relic_reward`; selected links distinguish them. Acquisition hooks execute in selected order. The current commitment policy excludes selected-offer toggles. |
| Meat Cleaver Cook | Select two cards at rest, then confirm, or cancel. Removing the same pair and applying the fixed max-HP gain commute in current code. The current policy blocks deselection and retains cancellation and potion actions. |
| Smith and shop removal | One immediate pick, with cancel where legal, including mandatory Lord's Parasol smithing. No selected-set confirmation loop. |
| Event deck choices | The shared Steps/Flow system and specialized Aroma of Chaos, Morphic Grove, Sapphire Seed, Wellspring and Whispering Hollow paths. Steps applies each pick immediately. Morphic Grove collects two picks before transforming them; their order can affect RNG results. |
| Card/removal rewards and event offers | Immediate choice/skip, or successive distinct choices where the event allows several. Acquisition order and hooks can matter; these are not all toggle selectors. |

The Steps/Flow deck-choice callers are Luminous Choir, Wood Carvings, Self Help
Book, Amalgamator, Doors of Light and Dark, Field of Man-Sized Holes, Grave of the
Forgotten, Spiraling Whirlpool, Spirit Grafter, Symbiote, Waterlogged Scriptorium,
Zen Weaver, Stone of All Time, Endless Conveyor and Trial. Their branches are in
[`act1_content.py`](../game/headless/events/act1_content.py),
[`roster.py`](../game/headless/events/roster.py),
[`minigames.py`](../game/headless/events/minigames.py) and
[`social.py`](../game/headless/events/social.py).

### Selection order is not universally interchangeable

The engine keeps selection order in
[`core/choices.py`](../game/headless/core/choices.py) and applies ordered effects
when confirming. Four regression tests in
[`test_selection_order.py`](../tests/agent/test_selection_order.py) show:

| Interaction | Same selected cards, different order |
| --- | --- |
| Neow's Fury | Strike then Defend versus Defend then Strike produces the corresponding hand order. |
| Astrolabe | With seed 2 and the same Strike, Injury and Secret Weapon selected, one order produces Sword Boomerang, Curse of the Bell and Panic Button; the reverse produces Splash, Curse of the Bell and Mangle. RNG is consumed per selected card. |
| Purity | Exhausting Drum of Battle then Strike versus the reverse, with Dark Embrace and a later Void draw, leaves **1 versus 2 energy**. Exhaust and draw hooks interleave. |
| Gambling Chip | Discarding Abrasive then Untouchable versus the reverse leaves **7 versus 6 block** through Sly autoplay. |

Simple deck removal, upgrading and enchanting the same selected identities
commute in the current pickup implementation. That does not generalize to ordered
draw/discard/exhaust effects, card acquisition or transformations. Claws can append
modified replacements in selected order. Pael's Tooth sorts by definition ID, but
equal-ID modified cards retain their relative selection order.

Order sensitivity does not make undo necessary for these deferred selectors.
Only confirmation applies their effects, so each final ordered subset has a
direct sequence of picks from an empty selector. The
[`commit-selection tests`](../tests/agent/test_commit_selection.py) exhaust the
native slot states for a three-option, zero-to-two-card Neow's Fury choice and
reach all ten ordered outcomes without undo. The four order-sensitive examples
above also run through the current policy. Attachment tests retain native slot
reuse without sorting inherited selections. This is headless evidence, not a
new live-game comparison.

Validation passed **723 agent/package-layout tests in 337.95 seconds**, including
31 new policy/selection-order cases, plus Python compilation. Tests cover real
selectors, separate select/confirm execution, cutoffs, policy-mask likelihoods,
serial and parallel PPO, imitation, exact resume, malformed versions and all
curriculum stages. Independent source/order review took 390 seconds; independent
implementation review, including the final corrections, took 403 seconds. Both
reviews closed without remaining blockers.

An installed two-worker PPO integration smoke completed 128 decisions in 3.73
seconds, followed by installed playback and evaluation. The 1.77-second artifact
audit checked all 128 recorded policy masks against canonical public decisions,
unchanged actor transfer, reward joins, checkpoint identity, eight further
trajectories and private-file permissions. This campaign smoke did not encounter
a filtered selector; the focused tests exercise those in both serial and parallel
collection. A read-only check of the three earlier imitation-loop observations
confirmed that identical actor weights now choose confirmation with probability
one where the original checkpoint chose deselection. These are immediate-decision
checks, not complete campaign reruns or evidence of improved win rate. Reports,
the audit script and validation log are retained in
`runs/policy-actions-20260929/`. No longer training experiment or native launch was
performed for this change.

## PPO signal guard and three-learner pilot

Every new PPO update now applies `skip_zero_signal_v1`. If all raw GAE advantages
are exactly zero, the learner replays the full rollout through the current model
and validates its original candidates, masks and chosen actions. It skips the
optimizer only if every current value prediction also exactly matches its return
target. The check counts residuals directly: a tiny nonzero error can have a
squared error that underflows to zero, and must still train. There is no threshold
that discards weak signals. Zero immediate rewards alone do not cause a skip;
bootstrapped value differences can still provide learning signal. Conversely,
an already perfectly predicted nonzero terminal reward can have no learning signal.

A skipped rollout performs no optimizer step, leaves all model tensors and Adam
state unchanged, and consumes no optimizer-shuffle RNG. It still advances the
completed-rollout count, processed-decision count and episode cursor so the next
collection uses fresh games. Cancellation or deadline expiry during validation
cannot commit that progress. This is a whole-rollout rule; updates containing
any learning signal continue to use the configured entropy regularization.

Each update records its status, skip reason, counts of nonzero advantages, return
targets and rewards, and the number of replayed value errors when that check is
needed. Reports separate `processed_decisions`, `trained_decisions`,
`skipped_decisions` and `skipped_updates`. Private PPO resume schema v3 binds the
update policy and skipped-iteration count. Its counter checks distinguish completed
rollouts from actual optimization iterations; old v1/v2 states retain their
original validation rules. Inference compatibility is unchanged, and exact resume
still requires matching sources and runtime.

The bounded development pilot uses the original full-run imitation actor, the
existing shaped reward preset and `commit_single_card_v1`. Its protocol was frozen
before campaign execution, including source, configuration, script and checkpoint
hashes plus a separate private seed registry:

- Sixteen genuine Ironclad A0 starts compare the original and filtered policies
  with identical model tensors and vocabulary; only the action-policy version
  differs. Eight starts use Overgrowth and eight use Underdocks.
- Three learners each receive 5,120 PPO decisions with two collectors, unchanged
  reward weights and hyperparameters, disjoint training episode ranges, and fresh
  optimizer/RNG state. The actor is retained and the shaped critic starts fresh.
  A 512-decision rollout is divided between the two workers, so a collected
  episode receives at most 256 decisions before its quota closes.
- Sixteen different starts, frozen at the same time, compare the filtered
  initializer with all three final checkpoints. Every final checkpoint is
  reported; there is no best-checkpoint selection or tuning on these cases.
- Campaign attempts have 4,096-action and 90-second limits. Cutoffs, defeats,
  abandonment and victory remain distinct, and every planned case stays in the
  denominator. Exact canonical replays measure confirmed combat outcomes using
  the adapter's allowlisted summary; replay seeds and engine state never enter
  the actor. Floor progress and shaped return are secondary measures.

The protocol and raw artifacts live in `runs/training-readiness-20260929/`, with
private data in its separate owner-only sibling directory. This is development
evidence in one imitation lineage, not held-out performance or native-game validation.

The paired filter comparison completed all 32 campaign attempts in 852.50 seconds,
including canonical replay and outcome analysis:

| Policy on the same 16 starts | Run wins | Selector-loop cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: |
| Original imitation | 0/16 | 5 | 7.69 | 49 |
| Identical actor with single-card commitment | 0/16 | 0 | 11.06 | 74 |

All five original cutoffs were floor-zero selection loops at the time limit. The
filter let those campaigns proceed; all filtered campaigns eventually ended in
defeat. The other eleven pairs had identical outcomes, floors and combat-win
counts. This establishes a progress benefit on the paired cases, without evidence
of increased run win rate.

All three shaped learners completed their 5,120-decision budget in ten batches.
The initial batches contained a few zero advantages; every later batch contained
512 nonzero advantages. No batch met the skip criterion, and no episode failed.

| Learner | Training seconds | Nonzero advantages / decisions | Confirmed combat wins during collection | Training defeats / quota cutoffs |
| --- | ---: | ---: | ---: | ---: |
| 1 | 107.58 | 5,114 / 5,120 | 210 | 42 / 19 |
| 2 | 105.00 | 5,109 / 5,120 | 204 | 38 / 20 |
| 3 | 105.98 | 5,114 / 5,120 | 213 | 38 / 20 |

Training took 318.57 seconds in total and produced no complete-run victories.
These collection results show that the shaped objective supplies learning signal;
they do not measure playing-strength improvement. Quota cutoffs bootstrap the
last ready observation and are recorded separately from defeats. The two-worker
256-decision episode horizon also limits exposure to later campaign decisions.

The separate final comparison completed all 64 planned campaign attempts in
844.87 seconds, including canonical replay and outcome analysis:

| Policy on the same 16 evaluation starts | Run wins | Time-limit cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: |
| Filtered initializer | 0/16 | 1 | 9.63 | 70 |
| Learner 1, final checkpoint | 0/16 | 0 | 10.31 | 93 |
| Learner 2, final checkpoint | 0/16 | 2 | 9.94 | 77 |
| Learner 3, final checkpoint | 0/16 | 0 | 10.69 | 86 |

Every non-cutoff campaign ended in defeat. The paired mean-floor differences
are +0.69, +0.31 and +1.06 respectively. These are descriptive progress gains;
all run-win differences remain zero with conservative paired 95% bounds of
approximately ±67.91 percentage points. The pilot establishes neither improved
run win rate nor equivalence. Do not compare these floor averages directly to
the earlier filter panel, which uses different seeds. No checkpoint was selected
or promoted from this development comparison.

The initializer's timeout was an optional, manually confirmed move-to-hand
selection with minimum zero and maximum two at floor 2. All three trained
policies completed that selection and later lost the campaign. Learner 2 instead
timed out on two other seeds by repeatedly opening and closing the same card
reward. Those reward-navigation loops were identified after observing the results
and are explicitly labeled as a post-hoc diagnostic, separate from the protocol's
select/deselect cutoff metric. Mandatory-single-card commitment does not cover
either optional/multiple-card selection or reward navigation.

The implementation passed **742 agent/package-layout tests in 352.95 seconds**,
including 18 new no-signal cases and legacy-resume coverage, plus Python
compilation. Focused checks also exercised tiny nonzero value errors, positive
but perfectly predicted terminal reward, warm Adam state, serial and parallel
collection, cancellation and exact resume. Independent reviews accepted the guard,
frozen protocol, analysis scripts and final interpretation. The [retained evidence](evidence/training_readiness_2026_09_29.json)
binds the protocol, all three learners, paired outcomes, validation and artifact
hashes; complete models, trajectories and scripts remain under ignored `runs/`.

A 67.32-second final artifact audit verified all 96 canonical campaign replays,
all 15,360 training decisions and their reward/action-mask joins, 177 unique
training episode reset seeds, and exact restore of all three final checkpoints.
All 310 private files had owner-only permissions and no partial artifacts remained.

## Act 1 training and configurable act rewards

The current curriculum objective is **Act 1 completion**, replacing full-campaign
victory as the near-term training and evaluation target. The policy controls the
whole first act: Neow, route choices, combat, rewards, shops, rests and events.
Both Overgrowth and Underdocks use genuine Ironclad A0 campaign starts.

The shared public boundary is `act_transition.completed_act == 1`. The engine
exposes it after the Act 1 boss has been defeated and its rewards have been
resolved or left. Training stops there, before `continue_act` enters Act 2.
This is task success (`terminated=True`, zero value bootstrap), including when
completion occurs on the last allowed action or at the time limit. A budget that
expires before an action remains a cutoff and earns no invented reward.
Canonical campaign trajectories retain their reached public decision and close
as `truncated/external_stop` with canonical reward zero. Reports separately
identify `act1_cleared`; an Act 1 success is never relabeled as an Architect victory.

Use the [Act 1 PPO preset](../configs/training/act1_ppo.json):

```bash
sts-agent-train ppo \
  --checkpoint runs/training-readiness-20260929/filtered-initializer.sts-model \
  --config configs/training/act1_ppo.json --output-dir runs/act1-ppo \
  --reset-objective --reset-action-policy --workers 2 --decisions 1024 --time-limit 120 \
  --seed 401 --start-index 700000
```

The preset uses reward schema `sts_full_run_reward_v3` with `goal: "act1"`.
The `full_run` mode/source identify the existing all-decision campaign pipeline;
the explicit goal sets its episode horizon. Goal and weights are both bound to
the objective identity in configuration, checkpoints and resume state. Changing
either requires `--reset-objective`: retain the actor/vocabulary, reset the critic
and optimizer, and start a new experiment. The historical filtered initializer
uses `commit_single_card_v1`; the current preset uses `commit_card_selection_v1`,
so this example also resets the action policy. To continue from an existing
Act 1 checkpoint with the same rewards, use only `--reset-action-policy` when
adopting the broader filter. Omit it once the checkpoint already uses that policy.

| Reward component | Preset weight |
| --- | ---: |
| `act_cleared` | +1.0 |
| `combat_win` | +0.1 |
| `win_hp_fraction` | +0.025 |
| `end_turn_action` | −0.001 |
| `run_defeat`, `run_abandoned` | −1.0 each |
| `run_victory`, `combat_loss`, `potion_use_action` | 0.0 |

Every weight is configurable. Act-clear success is measured independently of its
weight, so setting `act_cleared` to zero does not disable task termination or the
clear-rate metric. The preset collects 1,024 total decisions per rollout with a
512-decision episode cap. With two workers each gets at most 512 decisions;
remaining batch quota can still shorten a later episode. Time/decision cutoffs
remain separate from successes and defeats and retain their bootstrap values.

The new component also works in continuing full campaigns: use reward schema v3
with `goal: "full_run"` and the desired `act_cleared`/`run_victory` weights. Each
accepted transition into a newly completed act pays once. Reset/attachment,
`continue_act`, Architect entry and Architect victory do not repay it. A10's first
Glory boss does not pay an act bonus because the engine still requires its second
boss. Existing v1/v2 reward schemas retain their original weights and semantics;
they reject the new component until explicitly migrated to v3.

Compare a trained actor against a frozen initializer on identical Act 1 cases:

```bash
sts-agent-evaluate --act1 --checkpoint runs/act1-ppo/final.sts-model \
  --reference-checkpoint runs/training-readiness-20260929/filtered-initializer.sts-model \
  --output-dir runs/act1-evaluation --split validation --start-index 710000 \
  --campaign-cases 16 --max-decisions 1024 --time-limit 90 --workers 8
```

This evaluates heuristic, reference and learned policies on the same frozen
starts, alternating the two Act 1 regions. `act1-plan.json` is published before
the first action. `act1.json` reports `act1_clears`, `act1_clear_rate`, conservative
paired uncertainty, defeats, cutoffs, failures, unattempted cases and last observed
floor. `paired_vs_reference` is the direct improvement comparison. Every planned
case remains in the denominator. `--combat-checkpoint` can supply the existing
combat hybrid instead of a reference actor. The old `--full-run` evaluation keeps
its full-campaign victory metric. Choose fresh output directories and disjoint
episode ranges for follow-up runs; the example training budget is a bounded
integration run, not evidence that 1,024 decisions establish playing strength.

Use the splits according to how their results are consumed:

- `train` supplies learner updates and vocabulary fitting.
- `validation` supplies repeated checkpoint comparisons, reward experiments and
  development feedback. Reusing the same paired starts makes these comparisons
  easier to interpret.
- `test` supplies a fresh comparison after freezing checkpoint identities,
  action policies, case counts and success criteria. Check that its engine seeds
  have not appeared in retained training or earlier evaluations. Include every
  planned case and aggregate the fixed panel without adapting its size to results.

The split label alone does not establish independence. Once test outcomes guide
further tuning, treat those cases as development evidence for subsequent claims.
A fresh test panel measures generalization across starts; repeatability across
independently trained learners is a separate question.

Evaluation accepts `--workers 1` through `--workers 8` for both `--act1` and
`--full-run`; the default is serial. Each persistent worker loads frozen
checkpoint copies once, verifies their digests against the published plan and
uses one Torch thread. Every case/policy game has its own engine, seed and files.
The same case seed is reused across its three policies regardless of scheduling.
Canonical recording validation and outcome analysis also run in the worker;
the parent retains the fixed plan order and computes the paired summaries.
Evaluation workers are independent of the PPO collector and analysis exporter
worker settings. Other evaluation modes reject parallel worker requests.

The parent stops assigning games after failure or interruption, retains completed
acknowledgements from sibling workers and never retries a game. Interrupted and
unattempted rows remain in the planned denominator. Workers receive a cooperative
stop, followed by bounded forced cleanup if needed; forced terminations are
reported, and failed cleanup cannot produce a successful batch. Public failure
categories contain no private seed or exception text. The report/plan's
`execution` field records the scheduling mode, worker count and worker thread
count; existing public trajectory and Act 1/full-run report schemas are retained.

Gameplay still obeys each episode's configured decision/time limits. The parent
also guards worker startup (30 seconds) and a stuck game/analysis job (twice its
gameplay time limit plus 30 seconds). A worker deadline is an operational failure,
not a game defeat. For reproducibility comparisons, allow enough gameplay time:
host contention can make wall-clock cutoffs differ between worker counts even
when seeded decisions otherwise agree. Per-policy summed game time is distinct
from the complete evaluation's elapsed `total_seconds`, especially in parallel.

Matched evaluation benchmark (2026-09-29): the frozen 50k actor, its initializer
and the heuristic each played the same 16 performance-benchmark starts with one
worker and then eight. Each batch completed 48 games / 7,066 decisions. Evaluation
including canonical outcome validation took **288.55 seconds serially** and
**65.86 seconds with eight workers**, a **4.38× speedup**. Whole installed-command
elapsed time was 289.52 and 66.63 seconds respectively. This is one matched local
measurement, with serial measured first; it is not a general scaling guarantee.
Every initial state, transition record, outcome and non-timing metric matched.
Both runs retained all planned cases with no failures or time/decision cutoffs.
The learner's one genuine-start Act 1 clear in each batch also exercised the
successful public stopping boundary. These starts were used to measure throughput;
the result is not a new policy-selection or playing-strength claim.

The final affected regression gate passed **105 tests in 80.13 seconds**, and the
changed modules compiled successfully. Independent semantic review found no
blockers and took approximately 270 seconds, including acknowledgement-draining,
abrupt-exit and cancellation-cleanup probes. Independent artifact comparison took
1.25 seconds and checked paired seeds, canonical file/footer digests, unchanged
source/models, 98 owner-only private files and absence of partial recordings.
The [retained benchmark evidence](evidence/evaluation_parallel_2026_09_29.json)
binds source identities, measured timings, parity checks and the generated
artifacts under `runs/evaluation-parallel-20260929/`.

PPO rollout schema v4 retains the goal, all measured components and the previous
public act marker alongside the combat reward context. The collector checks the
marker against its original observation and verifies the terminal success against
the actual public successor. Task reports distinguish Act 1 clears from full-run
wins; private Act 1 runner audits use `sts_private_replay_v2` to bind the goal.
The public observation and canonical trajectory schemas are unchanged.

For one-policy playback, add `--act1` to `sts-agent-play --checkpoint PATH`.
The runner stops at the same public boundary and its batch summary reports
`act1_clears`; parallel playback preserves that goal for each worker.

Validation on 2026-09-29: all 758 agent/package tests passed in 364.33 seconds,
and `compileall game tests` passed. The 16 new Act 1 cases also passed separately
in 14.90 seconds. They cover configurable bonuses, actual boss-reward exits,
single-payment semantics across three acts, A10's two-boss boundary, successful
termination with zero bootstrap, coincident budgets, serial/parallel PPO,
checkpoint restore and paired evaluation failure denominators. Independent
read-only boundary and implementation reviews took 203 and 294 seconds;
the reviewer found no blockers and passed a separate 19-assertion semantic probe.

Installed-command smoke artifacts are in `runs/act1-training-20260929/`:
two-worker PPO processed/trained 128 decisions in 3.21 seconds and exact resume
processed/trained 16 more in 1.48 seconds. A two-case, three-policy paired
evaluation completed in 1.71 seconds; two-worker playback completed in 0.98
seconds. Evaluation/playback were capped at four actions per episode. The
1.02-second artifact audit validated all 13 canonical trajectories, all 144 PPO
reward joins, unchanged transferred actor weights, the fresh critic, both final
checkpoint restores, identical paired starts, 20 owner-only private files and
absence of partial artifacts. These are integration checks: they recorded no
Act 1 clears and do not establish a playing-strength improvement.

## Act 1 pilot (2026-09-29)

The first bounded Act 1 learning pilot is complete. Its protocol fixed the
initializer, reward preset, source identities, private seed registry and budgets
before the first baseline action. Sixteen fresh validation starts (eight per
region) were shared by the heuristic, filtered initializer and all three final
learners. The three training ranges were disjoint from one another, these
validation cases and the prior generated-headless audits checked during setup.
No hyperparameters were tuned during the pilot and no checkpoint was selected
or promoted. Raw protocols, models, trajectories and analysis scripts are under
`runs/act1-pilot-20260929/`; replay seeds and optimizer state are in its separate
owner-only sibling directory.

Each learner started from the same filtered actor, retained its vocabulary and
used a fresh Act 1 critic and optimizer. The unchanged Act 1 preset supplied
10,240 decisions in ten 1,024-decision rollouts, with two collectors and a
512-decision episode cap. All 30,720 decisions were processed and trained; no
batch met the zero-signal skip condition and no episode failed.

| Learner | Training seconds | Episodes | Act 1 clears | Defeats | Quota cutoffs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 218.38 | 99 | 1 | 78 | 20 |
| 2 | 215.38 | 105 | 0 | 85 | 20 |
| 3 | 218.56 | 99 | 0 | 79 | 20 |

Training took 652.32 seconds in total. The single genuine-start completion paid
the configured +1 bonus and ended with zero bootstrap. Only one of 303 collected
episodes supplied that success signal; these stochastic, quota-bounded training
outcomes are separate from final-policy validation.

Final greedy evaluation used a 1,024-action/90-second cap per attempt and retained
every planned case in the denominator. All 80 baseline/final attempts completed
with no execution failures or unattempted cases. The baseline panel took 388.11
seconds and the three-learner panel 530.51 seconds, including exact canonical
replay and outcome measurement.

| Policy on the same 16 starts | Act 1 clears | Defeats | Cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| Filtered initializer | 0/16 | 15 | 1 | 9.875 | 69 |
| Learner 1 | 0/16 | 16 | 0 | 11.375 | 101 |
| Learner 2 | 0/16 | 15 | 1 | 8.6875 | 80 |
| Learner 3 | 0/16 | 16 | 0 | 11.625 | 97 |
| Heuristic reference | 1/16 | 15 | 0 | 14.6875 | 109 |

There is **no observed Act 1 clear-rate improvement**. Paired clear-rate
differences are zero for all three learners; their conservative uncertainty
intervals span zero and do not establish equivalence. Floor differences versus
the initializer are +1.5, -1.1875 and +1.75. These descriptive gains for learners
1 and 3 do not establish consistent improvement across learner seeds.

The initializer and learner 2 each hit the action cap on the same optional,
manually confirmed zero-to-two-card move-to-hand selection at floor 1. Learner 1
advanced to floor 16 on that start. The planned tail-action check identified the
selector loops; no reward-navigation loops occurred in this panel. Mandatory
single-card commitment therefore remains useful but does not resolve this
optional selector. Successful Act 1 endings remain scarce even with dense combat
rewards. The next useful training stage is targeted Act 1 late-act/boss practice
and successful demonstrations, including completion of optional selections,
using training cases and retaining separate genuine-start evaluation.

The 217.79-second artifact audit verified all 30,720 PPO decisions and their
reward/action-mask joins, all 80 canonical evaluation replays, identical starts
across the five policies, 303 unique training episode seeds, all three exact
checkpoint restores and 420 owner-only private files. No partial artifacts
remained. Production sources, tests and dependencies were unchanged during this
pilot; the preceding 758-test validation was reused after verifying matching
implementation and runtime. Artifact manifest preparation took 1.16 seconds.
The [retained evidence](evidence/act1_pilot_2026_09_29.json) binds the frozen
protocol, all learner results, paired outcomes, audit and artifact hashes.

## Single-learner 50k experiment (2026-09-29)

The requested follow-up trained **one learner for 50,000 decisions with eight
parallel collectors**. It used the same imitation-trained actor and vocabulary
as the previous pilot, a fresh Act 1 critic and optimizer, and the current
`commit_card_selection_v1` policy. Rewards, both Ironclad A0 regions and the
512-decision episode cap followed the Act 1 preset.

The experiment increased `rollout_steps` from 1,024 to 4,096 so that eight
workers retained an allowance of 512 decisions each. Keeping the old rollout
size would have reduced each worker's allowance to 128. The final partial
rollout contained 848 decisions, or 106 per worker. The existing 20,000-decision
invocation limit was respected through three chunks of 16,384, 16,384 and
17,232 decisions, with exact checkpoint/optimizer/RNG/cursor resume between
chunks. These are continuations of one learner, not three independent learners.

All 50,000 decisions were trained in 13 PPO rounds and 6,250 optimizer steps,
with no skipped updates or failed episodes. Training took **428.54 seconds
(7m 9s), or 116.67 decisions/second**:

| Training phase | Seconds |
| --- | ---: |
| Parallel experience collection | 298.96 |
| Model updates | 126.69 |
| Other overhead | 2.89 |

There were **2 Act 1 clears in 493 training episodes**, alongside 388 defeats
and 103 quota/episode cutoffs. These sampled training outcomes do not measure
the final greedy policy's clear rate. The previous pilot averaged about 47
decisions/second, but the larger rollout batch, updated selection mask and new
game seeds mean this follow-up is not a matched-workload speed benchmark.

The final checkpoint was compared against its own initialization and the
heuristic on 16 fresh paired validation starts, eight in each region. The
initializer uses the same current selection mask as the final learner. This
isolates their learned-weight comparison from the selection-filter change;
neither reference is selected using evaluation results. Evaluation took
263.88 seconds (4m 24s).

| Policy | Act 1 clears | Defeats | Cutoffs | Mean last observed floor |
| --- | ---: | ---: | ---: | ---: |
| Heuristic | 0/16 | 16 | 0 | 13.25 |
| Initializer with current selection mask | 0/16 | 16 | 0 | 11.00 |
| Final 50k learner | 0/16 | 16 | 0 | 10.875 |

There is **no observed improvement** in Act 1 clear rate or mean floor against
the initializer. The paired clear-rate difference is zero, with the existing
conservative 95% interval spanning approximately ±67.91 percentage points.
One learner and 16 development starts do not establish policy equivalence or
general performance. Every planned case remains in the denominator; no
intermediate checkpoint was selected or promoted.

The resolved configuration, protocol, chunk reports and evaluation are under
`runs/act1-50k-8workers-20260929/`. The final inference bundle is
`chunk-03/final.sts-model`; the matching owner-only continuation state is
`runs/act1-50k-8workers-20260929-private/chunk-03/final.resume.pt`.
Use the experiment's saved `config.json` and eight workers for exact resume.
The [retained evidence](evidence/act1_50k_8workers_2026_09_29.json) records the
configuration, timings, checkpoint identities, results and artifact checks.

Post-experiment verification restored all three chunk checkpoints, confirmed
493 unique training episode seeds, and validated all 50,000 training decisions
against their canonical public recordings, including action masks and recomputed
rewards. The export verified identical public starts for all 16 evaluation cases.
All 562 private files retained owner-only permissions and no partial artifacts
remained. The analysis heuristics flagged no selection-toggle or reward-navigation
loops in the evaluation episodes; this is a check of these recordings, not a
general guarantee about future behavior.

The separate viewer export is `runs/act1-50k-8workers-20260929-analysis/`, with
541 episodes and 56,844 decisions. Verification and export took 473.97 seconds
(7m 54s), including 472.88 seconds for the export; this time is separate from
training and evaluation. Its `chunk-01`, `chunk-02` and `chunk-03` training groups
are consecutive segments of the same learner. Load the first chunk's
`initial.sts-model` and each chunk's `final.sts-model` to compare the initializer,
16,384-, 32,768- and 50,000-decision checkpoints on a recorded public state.

## Act 1 training throughput follow-up (2026-09-29)

A matched benchmark repeats the current Act 1 workload: **one learner, eight
persistent collectors, and 8,192 decisions in two 4,096-decision rounds**. Each
worker gets 512 decisions per round. Three fresh processes per version use the
same frozen initializer, private seed plan, rewards and optimizer configuration
as each other. The initializer and resolved configuration come from the 50k
experiment. Recording, every-round checkpoints and worker cleanup are included;
evaluation and analysis export are separate. Diagnostic profiler runs are excluded
from these timing medians.

| Measurement | Before | Optimized |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 71.70 s | **60.28 s** |
| Parallel collection, both rounds | 49.34 s | **40.04 s** |
| PPO updates, both rounds | 20.23 s | **18.20 s** |
| Decisions/second, including process overhead | 114.25 | **135.89** |
| First collection round, including worker startup | 25.37 s | 20.55 s |
| Second collection round, reusing workers | 23.97 s | 19.22 s |

The complete workload uses **15.9% less time**, or **18.9% more decisions per
second**. At this rate 50k decisions would take approximately **6m 8s**, excluding
evaluation and export. That is an extrapolation, not another measured 50k learning
experiment. Game lengths and later policy behavior can change throughput. Baseline
process times were 70.24–72.75 seconds; optimized times were 59.16–60.51 seconds.
OS caches and background host load were not controlled.

Profiling identified repeated Python schema inspection during public observation
conversion and repeated vocabulary hashing during PPO batch preparation. The
public codec now prepares bounded reusable schema readers and serialization field
layouts. It still validates every input and every public semantic invariant;
only schema work is reused. Union member ordering, exact primitive/Literal types,
recursive graphs and per-parse generic substitutions are preserved. The immutable
vocabulary computes its unchanged digest once when constructed, including after
loading a checkpoint. Model architecture, policy masks, sampling, rewards and
optimizer mathematics are unchanged.

Collection remains the main cost, around two-thirds of the complete process.
This pass does not reduce the retained observation payload: the two 4,096-step
rollouts contain 1.264 GB and 1.238 GB of packed data. Median parent peak RSS was
4.11 GB before and 4.15 GB after; those measurements exclude collector processes
and are not total pool memory.

Validation passed **635 focused contract, full-game projection, PPO, worker,
checkpoint, recording, Gym and encoding/package checks**, plus compilation and
diff checks. All six timing repetitions matched every recorded public state,
action and outcome, masks, likelihoods, values, rewards, advantages, returns,
non-timing update metrics and final model weights. An additional canonical reload
validated 176 baseline/optimized trajectories containing 16,384 decisions; all
652 generated private files/directories retained owner-only permissions, with
no partial artifacts. Independent semantic review found no blockers and compared 1,438
valid/malformed cases with the original codec, matching acceptance, decoded
values and error details. Inference bundles keep their wire format; exact
optimizer/RNG resume still requires the matching source build.

The raw protocol, source snapshots, profiles and reports are under
`runs/training-throughput-20260929/`. The
[retained evidence](evidence/training_throughput_2026_09_29.json) binds the inputs,
source identities, timing repetitions and validation results. These are throughput
checks; no checkpoint is selected or promoted for playing strength.

### Further snapshot copy optimization

The next pass reuses the preceding accepted three-repetition baseline and runs
three more repetitions of the identical eight-worker, 8,192-decision workload.
The benchmark script, initializer, configuration, private seed-plan digest,
runtime and host match; the source manifests differ only in the new private
snapshot copier and its two consumers.

| Measurement | Previous optimized build | With faster snapshot copying |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 60.28 s | **58.98 s** |
| Parallel collection, both rounds | 40.04 s | **38.94 s** |
| PPO updates, both rounds | 18.20 s | 18.27 s |
| Decisions/second, including process overhead | 135.89 | **138.88** |

This is **2.2% less total time** and **2.8% less collection time** in the measured
medians. The optimized range was 57.85–59.22 seconds, slightly overlapping the
baseline's 59.16–60.51 seconds; this is a modest result on one machine with
uncontrolled background load, not a guaranteed speedup. The linear 50k estimate
is now approximately **6m 0s**, excluding evaluation/export; no new 50k learning
experiment was run.

Private run/combat snapshots now use a detached dataclass copier that reuses
field-name metadata and directly returns exact immutable scalars. Mutable data
is still freshly copied, and namedtuples, container subclasses and custom leaf
copying retain the existing behavior. Snapshot validation, RNG capture/restore,
stale-action guards and snapshot schemas remain unchanged. Because the change
lives in the engine package, its source/rules digest changes legitimately;
historical evidence retains its original digest, and exact optimizer/RNG resume
still requires the matching build.

Validation passed **541 engine, snapshot/restore, public projection, recording,
PPO/parallel and package checks**. Independent semantic review found no blockers
and matched 315 differential cases against the standard copier. All six timing
repetitions matched every public transition, learning input, non-timing update
metric and final model weight, excluding only run identities and source/timing
metadata. Canonical reload independently validated 176 trajectories / 16,384
decisions against their original source bindings. All 327 new private
files/directories retained owner-only permissions; no partial artifacts remained.

The separate diagnostic profile still identifies public-observation conversion
and serialization as the largest remaining collection costs. Collection occupies
about two-thirds of the process, and the large packed rollout payload is unchanged.
An exploratory update-only probe with four Torch threads took 7.23 seconds versus
9.07 seconds with one thread, but produced different weights. The default remains
one thread; thread tuning needs a separately identified reproducibility/learning
comparison, and that single probe is not an end-to-end speed claim.

Raw reports, profiles and frozen source snapshots are under
`runs/training-snapshot-optimization-20260929/`. The
[retained evidence](evidence/training_snapshot_optimization_2026_09_29.json)
binds this result to the previous baseline, inputs, source changes and checks.

### Validated-observation reuse (2026-09-30)

Projection, encoding and PPO recording now share one prepared public observation.
Preparation validates and reconstructs canonical immutable records, including
canonical field order for structurally equivalent caller records. The owner
retains its serialized form; consumers requesting wire data receive independent
dictionary copies. Reuse requires the exact prepared decision object; equal-but-different
decisions cannot borrow another owner's validation. Owners stay with the current
frame/encoding and are released with the existing reset, failure and cleanup
paths. Nonterminal cutoffs and Act 1 completion retain their actual final decision.

The standard full-run and combat PPO paths use this automatically, as does the
built-in full-run Gym encoder. Custom encoders keep their own hooks and validating
fallback. Standalone unprepared inputs and disk recordings are still validated
independently. The recorder shares its action, execution, sequence, reward and
completion checks across both paths. Engine guards, game rules, RNG, model
architecture, policy masks, rewards and optimizer mathematics are unchanged.

Three **fresh** baseline repetitions and three optimized repetitions use the same
one-learner, eight-worker, 8,192-decision workload described above, including
recordings, checkpoints and cleanup. The baseline already includes the previous
optimizations; today's fresh measurements avoid comparing host conditions across
days. Medians are:

| Measurement | Fresh baseline | Prepared observations |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 56.69 s | **52.14 s** |
| Parallel collection, both rounds | 36.76 s | **32.11 s** |
| PPO updates, both rounds | 17.98 s | 18.07 s |
| Decisions/second, including process overhead | 144.50 | **157.13** |

Collection uses **12.6% less time**, and the complete process uses **8.0% less
time**. Baseline runs took 55.65–57.05 seconds; optimized runs took 50.31–52.53
seconds. Background load and OS caches remain uncontrolled. The linear estimate
for 50k decisions is **5m 18s**, excluding evaluation/export; this is a throughput
experiment, not a new 50k learning result or evidence of stronger play.

A separate 4,096-decision profile reduced full-public parsing calls from 16,534
to 4,180: approximately four passes per decision become one. The baseline
diagnostic profile has the exact matching source/runtime from the preceding
experiment; instrumented timings are excluded from the fresh throughput medians.
Canonical graph construction, tensor packing and stale-state guards remain
substantial costs. Packed rollout sizes are unchanged.

All **714 final regression tests passed**, covering contracts, ownership and
mutation isolation, custom encoders, encoding failures, full campaigns, recording,
analysis, PPO workers/checkpoints and package integration. Independent semantic
review found no blockers. All six timed runs matched every public transition,
mask, reward, value, likelihood, advantage, return, non-timing update metric and
final model weight. Canonical reload validated 176 trajectories / 16,384 decisions
against their original bindings; all 606 private files/directories retained
owner-only permissions, with no partial artifacts. Wire schemas and the engine's
rules digest are unchanged; exact optimizer/RNG resume still requires the matching
source build.

Raw reports and frozen sources are under
`runs/training-observation-reuse-20260930/`; the
[retained evidence](evidence/training_observation_reuse_2026_09_30.json) records
inputs, source identities, timing repetitions, profiles, checks and measured
phase timings.

### Direct prepared-observation encoding (2026-09-30)

The encoder now traverses the prepared owner's canonical immutable public records
directly, avoiding an intermediate dictionary copy. Field indexes are computed
once per packing operation. Both paths use the same ordered traversal, reference
registration, candidate sorting, capacity checks and array allocation. Canonical
dataclass field order and visible tuple order are preserved. Exact owner checks
still gate reuse; ordinary inputs and custom encoders retain validation, and
recorders still receive independent wire copies. No training configuration change
is needed to use this in standard combat/full-run PPO or the built-in full-run Gym
encoder.

Three fresh baseline repetitions and three optimized repetitions use the same
frozen initializer, configuration and seed schedule, with one learner, eight
workers and 8,192 decisions in two 4,096-decision rounds. Recording, checkpointing
and cleanup are included. This baseline already contains validated-observation
reuse and all preceding optimizations. Medians are:

| Measurement | Fresh baseline | Direct record encoding |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 51.35 s | **48.97 s** |
| Parallel collection, both rounds | 31.36 s | **29.21 s** |
| PPO updates, both rounds | 17.99 s | 18.01 s |
| Decisions/second, including process overhead | 159.54 | **167.28** |

Collection uses **6.9% less time**, and the complete process uses **4.6% less
time**. Baseline runs took 50.25–51.66 seconds; optimized runs took 48.26–49.48
seconds. A separate alternating-order packing probe on 137 recorded decisions,
701,308 tree rows and nine decision types took 0.514 → 0.393 seconds at the median
(23.6% less packing time), with exact arrays and action/reference bindings. That
probe excludes public preparation, inference, recording and PPO. Background load
and OS caches are uncontrolled in these measurements. The linear estimate for
50k decisions is **4m 59s**, excluding evaluation/export; it is not a new 50k
learning result or evidence of stronger play.

A separate 4,096-decision diagnostic profile reduced wire-copy calls from 8,208
to 4,104, retaining the recorder's copies. Encoding's share of profiled collection
time fell from 20.8% to 15.6%; public-observation construction (32.6%) and
stale-state guards (24.8%) remain larger costs. These instrumented measurements
are excluded from the throughput medians.

All **617 final regression tests passed**, covering v1/v2 encoding, prepared-owner
isolation, custom hooks, exact capacity errors, full public command families,
all five characters, both Act 1 regions, A0/A10, controlled complete campaigns,
recording, analysis consumers and PPO workers/checkpoints. Independent semantic
review found no blockers, including 810 additional differential cases against
the frozen pre-change encoder. All six timed runs matched every public transition,
mask, reward, value, likelihood, advantage, return, non-timing update metric and
final model weight. Canonical reload validated 176 trajectories / 16,384 decisions
with their original source bindings; all 606 private files/directories retained
owner-only permissions, with no partial artifacts. Game rules, stale-state guards, RNG, rewards,
model architecture and optimizer mathematics are unchanged. Exact optimizer/RNG
resume still requires the matching source build.

Raw reports and frozen source snapshots are under
`runs/training-encoding-optimization-20260930/`; the
[retained evidence](evidence/training_encoding_optimization_2026_09_30.json)
binds the inputs, source identities, timing repetitions and validation.

## Single-learner 250k learning curve (2026-09-30)

One learner trained for **250,000 decisions with eight workers**, starting from
the same frozen initializer as the 50k experiment. This was a fresh learner,
with a new optimizer/RNG and training starts; it did not continue the old 50k
weights. The 97,394-parameter model, vocabulary, Act 1 goal, selection policy
and reward weights were held fixed. Fifteen bounded invocations preserved the
model, optimizer, RNG and cursor across fourteen resume boundaries. Checkpoints
at 50k, 100k, 150k, 200k and 250k were declared before training.

All **250,000 decisions were trained**, in 65 PPO rounds and 31,250 optimizer
steps, with no failed episodes or skipped updates. The 2,393 sampled training
episodes contained 12 Act 1 clears, 1,867 defeats and 514 quota/episode cutoffs.
Recorded training combat outcomes were 11,136 victories and 1,855 defeats;
the additional run defeats occurred outside those combat-defeat measurements.

| Phase | Elapsed time |
| --- | ---: |
| Training, including collection and updates | 25m 43s |
| Parallel collection within training | 15m 43s |
| Model updates within training | 9m 46s |
| Five evaluation panels | 11m 36s |
| Verification, export and cross-panel comparison | 6m 53s |
| Preparing bounded viewer views | 14s |

Training averaged **162.1 decisions/second**. These are measured experiment
times; changed seeds and evolving policy behavior prevent treating comparisons
with the earlier 50k experiment as an isolated optimization benchmark.

All five checkpoints were evaluated after training on the **same 64 fresh,
paired headless Ironclad A0 starts**, 32 per region. Each panel reran the
initializer and heuristic, for 960 evaluation games in total. The 128 unique
baseline games reproduced identical public decisions and outcomes across all
five panels. Repeated baselines are not additional independent samples.

| Policy/checkpoint | Act 1 clears | Boss reached | Mean last observed floor | Cutoffs |
| --- | ---: | ---: | ---: | ---: |
| Heuristic | 0/64 | 26/64 | 12.00 | 0 |
| Frozen initializer | 0/64 | 6/64 | 9.67 | 0 |
| 50k | 1/64 | 19/64 | 10.58 | 0 |
| 100k | 4/64 | 31/64 | 12.19 | 2 |
| 150k | 2/64 | 22/64 | 10.77 | 0 |
| 200k | 10/64 | 32/64 | 12.56 | 0 |
| 250k, predetermined final endpoint | 8/64 | 28/64 | 11.88 | 1 |

Boss reach means the public map marks a boss node as visited. The final learner
cleared 4/32 starts in each region. Its observed clear-rate gain over the
initializer was **12.5 percentage points**, and it reached the boss much more
often. The curve is uneven: 200k had the highest observed clear count, while
250k regressed on both clears and mean floor. No checkpoint was promoted or
selected as a replacement based on these development results. One learner and
64 development starts do not establish repeatability; the existing conservative
paired 95% interval for the final clear-rate difference is approximately
**−21.45 to +46.45 percentage points**, so its formal verdict remains
`inconclusive` despite the positive observed result.

The analysis identifies concrete follow-up work. Repeated reward opening/closing
caused the two 100k cutoffs and the one 250k cutoff. No selection-toggle warning
was found in the evaluation recordings. At 250k, the descriptive
`end_turn_with_playable_card` flag appeared 97 times across 51/64 episodes;
the earlier four checkpoint panels had none. One final-policy recording,
`152abb937aa7472ab067fcc092c084fc`, step 4, ends a turn with one energy, zero
block, three legal Defends and seven displayed incoming damage. The initializer,
100k and 200k checkpoints prefer a Defend on that same public state. These
preferences and flags are review evidence; alternative outcomes were not
simulated. Inspect these behaviors and repeat the comparison with additional
learner seeds before increasing the budget again.

All training rewards and policy masks were checked against canonical public
recordings. Verification restored all fifteen saved continuation states,
confirmed 2,393 unique training reset seeds, checked paired public starts and
preserved owner-only permissions on 3,454 private files. All planned evaluation
games completed without operational failures, and no partial artifacts remained.
The experiment changed no production game, model or training implementation.

The [retained evidence](evidence/act1_250k_8workers_2026_09_30.json) contains the
resolved configuration, learning curve, per-region results, source/checkpoint
identities, review examples, timings and validation. Raw artifacts are under
`runs/act1-250k-8workers-20260930/`; the final bundle is
`chunk-15/final.sts-model`, and its owner-only continuation state is
`runs/act1-250k-8workers-20260930-private/chunk-15/final.resume.pt`.

The complete export retains **3,353 episodes / 386,016 decisions**. Its 104 MB
metadata file exceeds the viewer's existing 64 MiB limit, so five bounded views
reuse the validated decision chunks without changing that limit. Each contains
one 50k training block and its 192-game evaluation panel; all five together
preserve every episode. `viewer-views.json` binds their paths and hashes. Serve
the final view, optionally loading four explicitly named comparison bundles:

```bash
sts-agent-analyze serve runs/act1-250k-8workers-20260930-analysis-250000 \
  --port 8767 \
  --checkpoint initial=runs/act1-250k-8workers-20260930/chunk-01/initial.sts-model \
  --checkpoint 100k=runs/act1-250k-8workers-20260930/chunk-06/final.sts-model \
  --checkpoint 200k=runs/act1-250k-8workers-20260930/chunk-12/final.sts-model \
  --checkpoint 250k=runs/act1-250k-8workers-20260930/chunk-15/final.sts-model
```

Replace the view suffix with `050000`, `100000`, `150000` or `200000` to inspect
an earlier block. Evaluation policy labels keep the five panels separate.

## Interrupted extension toward 500k decisions (2026-09-30)

The requested extension reused the **250k final checkpoint exactly**, including
actor, critic, Adam state, both learner RNGs, counters and episode cursor. It kept
one learner, eight workers, the same Act 1 objective, reward weights, model and
action policy. The additional budget was 250,000 decisions, with planned new
checkpoints at 300k, 350k, 400k, 450k and 500k.

Training stopped on an engine fault at **378,672 trained decisions** after
13m 59.7s of additional training work. The successful extension contains 128,672
trained decisions in 33 completed rollouts, with no skipped updates. The failed
99th collection was discarded; its 324 received steps were not trained. The
last complete checkpoint retains 47,334 optimizer updates and iteration 98:

```text
runs/act1-500k-8workers-20260930/chunk-23/update-00098.sts-model
runs/act1-500k-8workers-20260930-private/chunk-23/update-00098.resume.pt
```

The failing episode reached a Haunted Ship with the player at 3 HP, the enemy
at 1 HP and Thorns active. Ending the turn killed both. Combat incorrectly
reported a player win, then reward generation rejected the dead player. A
separate diagnostic engine reproduced all 92 recorded transitions exactly before
the unique end-turn command reproduced the fault. The original failed adapter
was not retried; partial artifacts remain preserved. No production sources were
changed during that interrupted segment.

The already published 300k and 350k milestones were evaluated using the original
64 paired development starts, the frozen initializer and the heuristic:

| Checkpoint | Act 1 clears | Mean last observed floor | Cutoffs |
| --- | ---: | ---: | ---: |
| 250k, previous endpoint | 8/64 | 11.88 | 1 |
| 300k | 7/64 | 12.91 | 0 |
| 350k | 9/64 | 13.50 | 0 |

Both new panels completed without operational failures in 4m 31.1s combined.
The initializer and heuristic again cleared 0/64. These reused development
starts and one learner do not establish repeatability; the formal paired
conclusions remain `inconclusive`. No 400k, 450k or 500k result exists.

The [interrupted-extension evidence](evidence/act1_500k_interrupted_2026_09_30.json)
retains verified checkpoint continuity, completed-update accounting, panel
results and bounded analysis views. The frozen original protocol is retained
alongside a separately identified evaluation supplement for the two completed
milestones. The remaining budget at interruption was **121,328 decisions**.

Repairing the engine changes implementation identity. The existing exact-resume
guard intentionally rejects that change; continuing with saved actor and critic
weights and a fresh optimizer/RNG is a new, explicitly identified training
segment, not exact resume. Do not repin the old checkpoint or call the interrupted
experiment complete. The approved correction and continuation are recorded below.

## 500k continuation after the terminal-outcome fix (2026-09-30)

The user subsequently approved the engine fix and the fresh-optimizer
continuation. The corrected engine and snapshot validator prioritize player death
after normal revival effects. Nine new regression cases, replay of the saved
failure state and 745 focused engine/agent tests passed; an independent semantic
review found no blockers. The saved failure now produces a reconciled defeat,
zero victory components and a −1.001 training reward. Fairy/Lizard Tail and enemy
revival behavior remain covered. This is headless regression evidence, not a new
native gameplay capture.

The new segment is recorded separately under
`runs/act1-500k-fixed-8workers-20260930/`. It retains the 378,672-decision actor and
critic weights, uses a fresh optimizer, learner RNGs and disjoint training starts,
and resets its internal counters. Its checkpoints label **cumulative** decisions;
for example, 400k contains 21,328 decisions from the new segment. Model, reward,
action-policy and eight-worker PPO settings are unchanged. Only subsequent chunks
within the corrected source version use exact optimizer resume. The frozen
original protocol and failed artifacts are retained without modification.

The corrected segment completed all **121,328 additional decisions** in
**13m 34.0s**, reaching **500,000 cumulative trained decisions**. It recorded 955
training episodes, 36 Act 1 clears, 663 defeats and 256 cutoffs, with zero failed
episodes, skipped decisions or skipped updates. These are stochastic collection
results; checkpoint evaluation uses the separate paired development panel.

| Cumulative decisions | New-segment decisions | Checkpoint under the new segment root |
| --- | ---: | --- |
| 400,000 | 21,328 | `chunk-02/final.sts-model` |
| 450,000 | 71,328 | `chunk-05/final.sts-model` |
| 500,000 | 121,328 | `chunk-08/final.sts-model` |

Each final bundle has a corresponding owner-only `final.resume.pt` under the
same chunk in `runs/act1-500k-fixed-8workers-20260930-private/`. The final bundle's
SHA-256 is `cfe80fb0679bd7b0757081126ef99f8818fae6e1fe1a4a3faa3019811037a9e4`.
Internal learner counters describe this segment; the recorded lineage supplies
the prior 378,672 decisions. This is a cumulative training budget with a documented
engine correction and optimizer reset, not one uninterrupted optimizer trajectory.

The three planned checkpoints were evaluated on the same 64 genuine-start
development cases, with 32 from each Act 1 region. The initializer and heuristic
were rerun under the corrected engine. All **576 evaluation games** completed
without operational failures or decision cutoffs in **6m 59.8s**.

| Checkpoint | Act 1 clears | Boss reached | Mean last observed floor |
| --- | ---: | ---: | ---: |
| 350k, earlier engine/optimizer segment | 9/64 | 40/64 | 13.50 |
| 400k | 6/64 | 44/64 | 14.20 |
| 450k | 7/64 | 40/64 | 13.42 |
| 500k | 5/64 | 43/64 | 13.17 |

Both baselines again cleared 0/64. The 500k endpoint's observed clear rate is
**7.8125%**, below 350k's 14.0625%; this continuation does not demonstrate a
clear-rate improvement. The final paired interval against the initializer is
approximately **−26.14 to +41.77 percentage points**, retaining the formal
`inconclusive` verdict. The reused development panel, one learner and intervening
optimizer reset do not establish the cause of the variation. No checkpoint was
promoted or selected from the curve as a replacement for the planned endpoint.

The final learner cleared 3/32 Overgrowth and 2/32 Underdocks starts. Its
`end_turn_with_playable_card` review flag reappeared 77 times across 47/64 games,
versus zero at 400k and four at 450k. These are descriptive flags, not proof of
bad play; for example, ending with unused Defends against a stunned enemy can be
reasonable. A concrete review state is episode
`143c8f37bbb34540aaf9d5e3367a1c05`, step 4: one energy, zero block, three legal
Defends and 14 displayed incoming damage. The 500k policy prefers End Turn
(probability 0.326), while 350k/400k/450k prefer a Defend on the same state.
Alternative outcomes were not simulated. No selector-toggle or reward-navigation
loop flags appeared in these three evaluation panels.

All 121,328 new training decisions passed canonical recording, reward and
policy-mask validation. The initial actor/critic tensors match the saved 378,672
checkpoint exactly; the empty optimizer and new RNG/cursor were verified. Seven
subsequent resume boundaries and all eight chunk endpoints were checked, with
eight-worker allocation throughout. The three panels' 64 public starts and 128
baseline decision traces match one another and the prior panel; their new source
identity remains distinct. The failed original collection is retained separately.

Verification and export took **4m 04.1s**. Three bounded views retain **1,531
episodes / 204,347 recorded decisions**, including all successful training updates
and the 576 evaluation games. Each respects the existing 64 MiB metadata limit.
The [retained evidence](evidence/act1_500k_corrected_2026_09_30.json) binds the
source correction, tests/review, initialization, complete learning curve,
checkpoint identities, timings, viewer views and review example. To inspect the
final view with all four comparison checkpoints:

```bash
sts-agent-analyze serve runs/act1-500k-fixed-8workers-20260930-analysis-500000 \
  --port 8769 \
  --checkpoint 350k=runs/act1-500k-8workers-20260930/chunk-21/final.sts-model \
  --checkpoint 400k=runs/act1-500k-fixed-8workers-20260930/chunk-02/final.sts-model \
  --checkpoint 450k=runs/act1-500k-fixed-8workers-20260930/chunk-05/final.sts-model \
  --checkpoint 500k=runs/act1-500k-fixed-8workers-20260930/chunk-08/final.sts-model
```

## Combat reward comparison from scratch (2026-09-30)

The user requested higher combat-win and remaining-HP rewards, then explicitly
chose to start from scratch. The comparison in
`runs/act1-combat-reward-ab-20260930/` uses two matched arms:

| Component | Current-reward control | Increased combat rewards |
| --- | ---: | ---: |
| `combat_win` | +0.1 | +0.2 |
| `win_hp_fraction` | +0.025 | +0.1 |
| `act_cleared` | +1.0 | +1.0 |
| `run_defeat`, `run_abandoned` | −1.0 each | −1.0 each |
| `end_turn_action` | −0.001 | −0.001 |
| All other components | 0 | 0 |

Both actor and critic are freshly constructed from the same random initialization.
No imitation or PPO parameters are copied from the previous 500k model. Only the
existing architecture, frozen observation vocabulary, action-policy version and
control settings are reused; even the vocabulary's embedding weights are random.
Both arms begin with an empty optimizer, identical learner RNGs and the same
reserved training-start range, disjoint from the checked prior experiments and
evaluation starts. The initialized tensors are checked against an independently
constructed fresh model and against each other before collection.

Each arm has one learner, eight collection workers and **100,000 decisions from
zero**, with checkpoints at 50k and 100k. Arms run sequentially. The existing
4,096-step PPO rollout and 512-decision episode cap remain unchanged, and bounded
chunks use exact resume only within their own arm. These counts do not inherit
the previous model's 500k decisions. The frozen protocol sets the 100k paired
Act 1 clear-rate difference as the primary endpoint; 50k is descriptive.

Evaluation uses the same 64 development starts as the earlier learning curve,
with 32 per Act 1 region, a 1,024-decision limit and eight workers. Each panel
runs the current-reward checkpoint, increased-reward checkpoint and heuristic.
Raw training returns have different scales and are not a performance comparison.
One learner seed, reused development cases and changing both weights together
limit conclusions about repeatability, generalization and either reward alone.
The existing reward/Act 1 tests passed **41 checks in 21.32 seconds**; no
production implementation changed for this experiment.

Both arms completed all 100,000 decisions without failed episodes or skipped
updates. The control took **10m 04.3s** and the increased-reward arm **10m 07.1s**,
for **20m 11.5s** total. Collection recorded 1/1,103 Act 1 clears for the control
and 3/1,151 for increased rewards; quota/episode cutoffs were 207 and 206. The
first 4,096 collected actions, masks, values and outcome components match exactly
between arms, before their different rewards affect the first PPO update.

All **384 evaluation games** completed without operational failures in
**5m 33.9s**:

| Decisions from scratch | Control Act 1 clears | Increased-reward Act 1 clears | Control / increased cutoffs |
| --- | ---: | ---: | ---: |
| 50,000 | 0/64 | 2/64 | 0 / 0 |
| 100,000 | 1/64 | 10/64 | 0 / 3 |

At the primary 100k endpoint, the observed difference is **+14.06 percentage
points** (15.625% versus 1.5625%). Ten paired cases cleared only with increased
rewards and one only with the control. The existing conservative paired 95%
interval is −19.89 to +48.02 percentage points, so its formal conclusion remains
`inconclusive`. The observed gain is promising, but one learner seed on reused
development cases does not establish a reliable improvement. This matched
from-scratch comparison does not isolate why the earlier warm-started 500k model
performed differently.

The increased-reward policy's three cutoffs all hit the 1,024-decision limit
while repeatedly opening and closing card rewards, on floors 14, 13 and 3.
They remain non-wins in the denominator. These are reward-navigation loops,
not selector deselection loops; no policy or engine change was made during the
experiment to remove them. Measured post-win HP during training averaged 64.37%
for the control and 65.62% for increased rewards, but these on-policy samples
include different fights and are not a matched damage-reduction estimate.

Both planned checkpoints and every closed-update checkpoint are retained. The
100k endpoints are `control/chunk-06/final.sts-model` and
`increased/chunk-06/final.sts-model`; the 50k endpoints use `chunk-03` instead.
Matching private optimizer/RNG state is under the same paths in
`runs/act1-combat-reward-ab-20260930-private/`.

At 100k, the control reached the boss in **26/64** games and increased rewards
in **32/64**. Increased rewards cleared 6/32 Overgrowth and 4/32 Underdocks starts;
the control cleared 1/32 and 0/32. Mean last observed floor was 12.05 versus
12.44. HP after observed living combat exits averaged **68.65% versus 68.14%**,
so this diagnostic does not show a higher remaining-HP fraction despite the
clear-rate gain. It includes automatic healing and different encountered fights,
and excludes any instantaneous fight without a projected combat state. Neither
learned checkpoint produced end-turn-with-playable-card or selector-toggle flags
in either evaluation panel; the three reward-navigation flags remain.

Full verification/export took **6m 38.3s**. It checked the fresh initialization,
all 12 exact-resume boundaries and endpoint states, all **200,000 training
decisions**, and 128 paired cases across the two evaluation panels. Six bounded
views retain **2,638 episodes / 258,914 recorded decisions**, within the existing
64 MiB metadata limit. Production sources remained identical to the corrected
500k implementation. The [experiment evidence](evidence/act1_combat_reward_scratch_ab_2026_09_30.json)
binds configurations, initialization, checkpoints, source identity, timings,
record validation, paired results, the six views and checked viewer examples.

The final evaluation view is available locally on port 8770. It includes the
untrained policy and both reward variants for same-state comparisons; critic
values use different reward scales and must not be compared as clear probabilities.
To restart it:

```bash
sts-agent-analyze serve runs/act1-combat-reward-ab-20260930-analysis-eval-100000 \
  --port 8770 \
  --checkpoint 'Untrained=runs/act1-combat-reward-ab-20260930/control/start.sts-model' \
  --checkpoint 'Current rewards 100k=runs/act1-combat-reward-ab-20260930/control/chunk-06/final.sts-model' \
  --checkpoint 'Increased rewards 50k=runs/act1-combat-reward-ab-20260930/increased/chunk-03/final.sts-model' \
  --checkpoint 'Increased rewards 100k=runs/act1-combat-reward-ab-20260930/increased/chunk-06/final.sts-model'
```

Episode `9b874e98c6ba405598d246fc505f370b` is an increased-reward Underdocks clear.
Episode `2b2edfda06e1478fbbace76f3d66e1e9`, step 37, starts the floor-3 reward
navigation loop. These are public recording and inference examples; alternatives
were not simulated in that experiment. The following frozen-weight ablation
addresses those loops separately. Repeating the reward comparison with another
learner seed and fresh evaluation starts remains necessary before treating the
weights as a reliable improvement.

## Reward-navigation filter and frozen-weight evaluation (2026-09-30)

The user approved fixing the observed reward open/close loops in the shared
policy-action layer and re-evaluating both 100k checkpoints without training.
`commit_decisions_v1` composes the existing ordered selector commitment with the
[card-reward inspection rule](#shared-policy-actions-and-selection-order).
Both current training presets adopt this new identity; reward weights, engine
rules, public legal candidates and the old policy versions remain unchanged.

The experiment in `runs/act1-reward-navigation-20260930/` copies every actor and
critic tensor exactly into a separately named policy bundle for each arm. The
new bundles use existing PPO serialization with a fresh, unused optimizer and
zero new-experiment counters. Their lineage explicitly records **100k prior
training decisions and zero additional training**. This is an inference
ablation, not an exact optimizer continuation. Original checkpoints and earlier
recordings retain their original bytes and identities.

Each arm is evaluated before and after filtering on the same 64 development
starts, with eight workers, the existing 1,024-decision cap and the unchanged
heuristic baseline. All **384 games** completed without operational failures in
**6m 13.6s**:

| Frozen 100k model | Original Act 1 clears | Filtered Act 1 clears | Reward-loop cutoffs, original → filtered |
| --- | ---: | ---: | ---: |
| Current-reward control | 1/64 | 1/64 | 0 → 0 |
| Increased combat rewards | 10/64 | 11/64 | 3 → 0 |

The three originally stuck runs now resolve their rewards with an explicit card
choice. The floor-14 Underdocks run clears Act 1 in 206 decisions. The other two
subsequently lose, in 206 and 190 decisions, instead of consuming all 1,024 steps.
Only those three trajectories change: all other **61 increased-reward runs and
all 64 control runs** retain identical decisions and public observations. The
128 original-policy replays also exactly reproduce the earlier recordings. Each
first divergence is the previously repeated close, at steps 159, 149 and 40.
Same-state inference confirms zero probability for that close and identical
critic values; only the policy permission changes. The filtered panels contain
no reward-navigation, selector-toggle or unused-playable-card review flags.

The observed clear-rate increase is one game, not evidence of a repeatable
learning improvement. Both comparisons retain the conservative `inconclusive`
paired verdict on this reused development panel. Coverage is limited to known
card-reward modals; removal and unknown shapes retain their exits. The next
learning experiment should use the new policy from the outset in both reward
arms, with another learner seed and fresh evaluation starts.

Validation passed **303 targeted tests in 67.02s**, compilation and diff checks,
plus an independent semantic review of public inputs, order/legality and
checkpoint compatibility. Tests include rerolls, multiple reward inspection and
resolution order, incomplete history/unknown shapes, selection order, PPO worker
collection/replay, imitation, checkpoint playback and resume/reset behavior.
Recording validation/export took **1m 25.5s**, producing two bounded views with
**384 games / 65,224 decisions**. The
[retained evidence](evidence/act1_reward_navigation_filter_2026_09_30.json)
binds sources, checkpoint lineage, tests/review, paired traces, timings and the
checked viewer endpoints.

The increased-reward before/after viewer runs locally on port 8771. Episode
`3262ba1c6e6f4c5c9f436893c9663e99`, step 159, shows the repaired decision in the
run that subsequently clears Act 1. To restart it:

```bash
sts-agent-analyze serve runs/act1-reward-navigation-20260930-analysis-increased \
  --port 8771 \
  --checkpoint 'Original increased 100k=runs/act1-combat-reward-ab-20260930/increased/chunk-06/final.sts-model' \
  --checkpoint 'Filtered increased 100k=runs/act1-reward-navigation-20260930/increased/frozen-100k.sts-model' \
  --checkpoint 'Original control 100k=runs/act1-combat-reward-ab-20260930/control/chunk-06/final.sts-model' \
  --checkpoint 'Filtered control 100k=runs/act1-reward-navigation-20260930/control/frozen-100k.sts-model'
```

## Increased-reward continuation to 250k decisions (2026-09-30)

The user requested extending the learner to **250,000 total decisions**. The
experiment in `runs/act1-increased-250k-8workers-20260930/` continues the
increased-reward 100k actor/critic for **150,000 additional decisions**, with one
learner and eight workers. It retains `combat_win = 0.2`,
`win_hp_fraction = 0.1`, `act_cleared = 1`, defeat/abandonment at −1 and end-turn
cost at −0.001. The architecture, vocabulary and engine rules remain unchanged.

The continuation uses `commit_decisions_v1`. Every starting tensor matches the
original increased-reward 100k checkpoint, through its frozen filtered bundle.
Because the original training used the earlier action policy, this segment
starts with a fresh optimizer, learner RNG and disjoint reserved training range.
It does not claim uninterrupted optimizer continuation from the original 100k.
All nine bounded chunks then use exact resume within this segment. The protocol
fixes the total budget and 150k/200k/250k endpoints before training; no intermediate
result changes the budget or reward settings.

All **150,000 additional decisions** were accepted and trained, with **zero failed
episodes and zero skipped updates**, in **16m 51.7s**. The 1,160 sampled training
episodes include 27 Act 1 clears, 825 defeats and 308 quota/episode cutoffs. Clears
in consecutive 50k blocks were 3, 9 and 15; these stochastic on-policy counts are
descriptive and are not the paired evaluation measure.

Evaluation compares each checkpoint with the filtered 100k initializer and the
heuristic on the same 64 development starts, split evenly between Overgrowth and
Underdocks. All **576 games** completed without operational failures or cutoffs
in **8m 21.3s**, with eight workers:

| Total training decisions | Act 1 clears | Clear rate | Mean last observed floor |
| --- | ---: | ---: | ---: |
| 100k filtered initializer | 11/64 | 17.19% | 12.69 |
| 150k | 8/64 | 12.50% | 12.42 |
| 200k | 9/64 | 14.06% | 13.95 |
| 250k, planned final endpoint | 17/64 | 26.56% | 13.97 |

The final observed gain is **six clears / 9.375 percentage points** over the
initializer. Ten paired starts clear only with the 250k model and four only with
the initializer. The conservative paired 95% interval is approximately −24.58 to
+43.33 percentage points, retaining the formal `inconclusive` verdict. One
learner and reused development starts do not establish repeatability or
generalization. The two earlier checkpoints regressed on clear rate, so this
extension also demonstrates that the learning curve is not monotonic.

The retained checkpoints are `chunk-03/final.sts-model` (150k),
`chunk-06/final.sts-model` (200k), and `chunk-09/final.sts-model` (250k). Matching
private resume states use the same relative paths under
`runs/act1-increased-250k-8workers-20260930-private/`. Resume counters record this
150k segment; the experiment lineage separately records the inherited 100k.

Boss reach rose from **34/64** for the initializer to **44/64** at both 200k and
250k. The final model clears 10/32 Overgrowth starts and 7/32 Underdocks starts.
HP at observed living combat exits averages 69.95%, versus 67.88% for the
initializer; these are different fights and include healing, so they are not a
matched damage-reduction estimate. No selector-toggle or reward-navigation flags
appear in the evaluation panels. End-turn-with-playable-card flags number 52
across 39 games at 150k, zero at 200k, and 34 across 30 games at 250k.

One concrete review state is episode `00ccf836da244230a56802aff30c9412`, step 5:
one energy, zero block, two legal Defends and 14 displayed incoming damage. The
250k policy ends the turn and the recorded successor loses 14 HP. Same-state
comparison shows the 100k and 200k models prefer a Defend, while 150k and 250k
prefer End Turn (probabilities 0.567 and 0.531). This is a useful review target;
the flags alone do not prove every flagged action is a mistake, and alternative
actions were not simulated. Episode `15b85fe0b4e74b8d8636ad181a3ca0e2` is one of
the ten final-model clears on a start where the initializer loses.

Initialization and all nine exact-resume transitions/endpoints were verified.
All **150k new training decisions** passed canonical observation, reward and
policy-mask validation. Across the three panels, all 64 public start states match,
and all 384 initializer/heuristic replays reproduce the parent baseline traces.
The unchanged 303-test source/runtime evidence from the filter implementation is
reused; no production code changed for this experiment. Full validation/export
took **6m 55.1s**. Six bounded views retain **1,736 episodes / 244,375 decisions**,
including every new training decision and all 576 evaluation games. The
[experiment evidence](evidence/act1_increased_250k_2026_09_30.json) binds the
protocol, lineage, checkpoints, source/runtime, validation, timings, learning
curve and viewer examples.

The final viewer runs locally on port 8772 with all four same-reward checkpoints:

```bash
sts-agent-analyze serve runs/act1-increased-250k-8workers-20260930-analysis-eval-250000 \
  --port 8772 \
  --checkpoint '100k initializer=runs/act1-reward-navigation-20260930/increased/frozen-100k.sts-model' \
  --checkpoint '150k=runs/act1-increased-250k-8workers-20260930/chunk-03/final.sts-model' \
  --checkpoint '200k=runs/act1-increased-250k-8workers-20260930/chunk-06/final.sts-model' \
  --checkpoint '250k=runs/act1-increased-250k-8workers-20260930/chunk-09/final.sts-model'
```

## Held-out Act 1 test (2026-09-30)

After reviewing the development results, the user approved a fresh comparison
of the frozen 250k endpoint against the filtered 100k initializer. The protocol
in `runs/act1-heldout-250k-20260930/` fixes **256 test starts**, with 128 per Act 1
region, before any game is played. Four fixed 64-case batches respect the existing
evaluator's per-call limit. Eight workers run both checkpoints and the usual
heuristic on every case, for **768 games**. There is no training, intermediate
checkpoint search, reward change or adaptive sample-size adjustment.

All 256 engine seeds are disjoint from the retained experiment metadata checked
at preparation: 18,789 replay audits and 27 case files under `runs/`. The
checkpoints, action policy, source/runtime and sample size are bound in the
published protocol; replay seeds remain in private experiment files. Each
trajectory is labelled `test`. This is a new-start test of one trained learner,
not a repeat of training with independent learner seeds.

| Frozen policy | Act 1 clears | Clear rate | Overgrowth | Underdocks |
| --- | ---: | ---: | ---: | ---: |
| Filtered 100k initializer | 23/256 | 8.98% | 13/128 | 10/128 |
| 250k endpoint | 56/256 | 21.88% | 35/128 | 21/128 |
| Heuristic | 14/256 | 5.47% | 4/128 | 10/128 |

The observed paired gain is **33 clears / 12.89 percentage points**: 42 cases
clear only with the 250k model and nine only with the initializer. The gain
appears in both regions and extends beyond the reused development cases.
The predeclared source-group Hoeffding 95% interval is **−4.09 to +29.87 percentage
points**, retaining the protocol's formal `inconclusive` conclusion. This
conservative interval and one learner do not establish training repeatability.
The earlier 64-case panel remains validation evidence; its percentages should
not be pooled with this independently chosen test panel.

Boss reach increases from **132/256 to 191/256**. The 250k recordings contain
133 end-turn-with-playable-card review flags across 114 games; these remain
diagnostics, not proof that every flagged action is a mistake. No selector-toggle
or reward-navigation flags appear in any of the three policies' test recordings.

All **768 games** completed without cutoffs, operational failures or unattempted
cases in **11m 30.1s**. All **128,391 decisions** passed canonical recording
validation, and all **256 paired starts** matched. Validation/export took
**2m 36.1s**. Source, checkpoint and runtime/dependency bindings remain unchanged;
the prior 303-test evidence is reused, not rerun. The
[held-out evidence](evidence/act1_heldout_250k_2026_09_30.json) records the frozen
protocol, identities, summaries, validation and timings. Once these test outcomes
guide further changes, use a fresh panel for the next independent test claim.

The test viewer retains all 768 games and both frozen model comparisons:

```bash
sts-agent-analyze serve runs/act1-heldout-250k-20260930-analysis \
  --port 8773 \
  --checkpoint '100k initializer=runs/act1-reward-navigation-20260930/increased/frozen-100k.sts-model' \
  --checkpoint '250k=runs/act1-increased-250k-8workers-20260930/chunk-09/final.sts-model'
```

## Increased-reward continuation to 500k decisions (2026-09-30)

The user requested extending the current increased-reward 250k learner to
**500,000 total decisions**. The experiment in
`runs/act1-increased-500k-8workers-20260930/` adds **250,000 decisions** with one
learner and eight workers. It preserves `combat_win = 0.2`,
`win_hp_fraction = 0.1`, `act_cleared = 1`, defeat/abandonment at −1 and end-turn
cost at −0.001, together with `commit_decisions_v1`, the model architecture,
vocabulary and engine rules.

This is an **exact resume from 250k**: actor, critic, Adam moments, both learner
RNGs, sampling cursor and worker allocation carry forward. The start checkpoint
round-trip retains the parent's semantic private-state digest. There is no new
optimizer or objective reset. The original 100k policy-change reset remains in
the earlier lineage; internal resume counters finish at 400k and the inherited
100k offset makes the reported total 500k. Before collection, the next 250k
reserved engine seeds were checked against retained experiment audits/case files,
the validation panel and the recent 256-case test panel, with zero overlap.

All **250,000 new decisions** were accepted and trained in **29m 7.5s**, with no
failed episodes, skipped updates or skipped decisions. The 1,732 training
episodes contain 164 Act 1 clears, 1,050 defeats and 518 rollout-quota/episode
cutoffs. The latter remain bootstrapped training cutoffs. Clears in consecutive
50k blocks were **17, 32, 32, 34 and 49**; these stochastic training counts are
descriptive, not the fixed-policy validation measure.

The protocol fixes checkpoints at **300k, 350k, 400k, 450k and 500k** before
training, retained respectively in `chunk-03`, `chunk-06`, `chunk-09`, `chunk-12`
and `chunk-15` as `final.sts-model`. Every update also retains an inference bundle
and owner-only resume state. Private counterparts use the matching paths under
`runs/act1-increased-500k-8workers-20260930-private/`.

Validation compares all five milestones with the frozen 250k parent and heuristic
on the existing 64 development starts, 32 per region. All **960 games** complete
without operational failures, unattempted cases or cutoffs in **14m 45.7s**, with
eight workers:

| Total training decisions | Act 1 clears | Clear rate | Mean last observed floor |
| --- | ---: | ---: | ---: |
| 250k frozen parent | 17/64 | 26.56% | 13.97 |
| 300k | 14/64 | 21.88% | 14.00 |
| 350k | 9/64 | 14.06% | 14.06 |
| 400k | 21/64 | 32.81% | 14.67 |
| 450k | 20/64 | 31.25% | 14.23 |
| 500k, planned final endpoint | 18/64 | 28.13% | 14.47 |

The planned 500k endpoint gains **one clear / 1.5625 percentage points** over
the parent. Nine paired starts clear only at 500k and eight only at 250k. The
conservative paired 95% interval is **−32.39 to +35.52 percentage points**,
retaining the formal `inconclusive` verdict. This run demonstrates completion
and checkpoint continuation, with little final clear-rate gain on this panel.
The 400k checkpoint has the highest observed validation score and remains a
descriptive intermediate result; it is not automatically promoted over the
predeclared endpoint. The learning curve is visibly non-monotonic.

The recent 256-case held-out test panel is excluded from collection and these
validation runs. Results remain development evidence; this extension does not
claim a new held-out test or repeatability across learner seeds.

The final model reaches the boss in **50/64 games**, versus 44/64 for its parent,
and clears 7/32 Overgrowth and 11/32 Underdocks starts. Living combat-exit HP
averages 72.42%, versus 69.95% for the parent; this includes different fights and
healing and is not a matched damage-reduction estimate. End-turn-with-playable-card
flags number 0, 0, 0, 3 and 69 at the five milestones, versus 34 for the parent.
The 500k flags occur across 36 games. They identify review candidates, not proven
strategic mistakes. Selector-toggle and reward-navigation flags remain absent.

All **15 exact-resume transitions and final resume states** verified successfully.
The exporter canonically validates all **250k new training decisions**, including
rewards and policy masks, and all **960 evaluation games / 163,041 decisions**.
Across the five panels, all 64 paired public starts match, and **640 baseline
replays** reproduce the parent's recorded traces. Ten bounded views retain
**2,692 episodes / 413,041 decisions**. Full validation/export takes **12m 7.7s**.
The unchanged 303-test source/runtime/dependency evidence is reused; no production
code changed. The [experiment evidence](evidence/act1_increased_500k_2026_09_30.json)
binds the protocol, checkpoint lineage, validation, timings and complete curve.

The final viewer loads the parent and three later milestones for same-state
comparison; all five training milestones and validation exports remain retained:

```bash
sts-agent-analyze serve runs/act1-increased-500k-8workers-20260930-analysis-eval-500000 \
  --port 8774 \
  --checkpoint '250k parent=runs/act1-increased-250k-8workers-20260930/chunk-09/final.sts-model' \
  --checkpoint '400k=runs/act1-increased-500k-8workers-20260930/chunk-09/final.sts-model' \
  --checkpoint '450k=runs/act1-increased-500k-8workers-20260930/chunk-12/final.sts-model' \
  --checkpoint '500k=runs/act1-increased-500k-8workers-20260930/chunk-15/final.sts-model'
```

## Implementation sequence and next experiment

1. Milestones 1 and 2 established combat episodes, measured baselines,
   configurable rewards and faithful training records, with results reviewed
   between the user-authorized milestones.
2. Milestone 3 delivered the first usable combat checkpoint and began bounded
   hybrid full-run evaluation with heuristic non-combat decisions.
3. Milestones 4 and 5 added combat PPO, curriculum and paired evaluation, with
   hybrid development evaluations at selected checkpoints.
4. Milestone 6 extended the validated pipeline to full-run learning. The first
   full-run pilot demonstrated integration without improved campaign performance.
5. Commands arrived as each stage became usable; milestone 7 completed their
   installation and delivery checks.

The delivered baseline is combat-first Ironclad A0, terminal-win reward, optional
objective weights, a candidate-scoring actor-critic, imitation warm-up and masked
PPO. Resolved configs, architecture settings, dependencies and measured results
are recorded above. Hardware and larger compute budgets remain experiment
settings; cloud jobs, native game launches, live corpus collection and
profile/save access are outside this implementation's scope.

The signal guard, paired filter comparison, shaped campaign pilots and cumulative
500k Act 1 training budget are complete. The terminal-outcome fix and authorized
optimizer reset remain explicit in the checkpoint lineage. Act 1 remains the
current training target:

1. Review paired regressions between the 250k parent and 500k endpoint on the
   existing validation cases, using 400k as a diagnostic intermediate. Inspect
   end-turn and late-combat decisions to choose one concrete follow-up hypothesis.
   Judge progress by Act 1 clear rate, with boss reach, floors, combat outcomes
   and cutoffs as diagnostics. Retain the completed 250k held-out result as its
   original evidence; use fresh test cases for a later frozen comparison. Preserve
   ordered outcomes, native legality and public inputs in any policy change.
2. Repeat the bounded, predeclared reward comparison from scratch with
   `commit_decisions_v1` in both arms and another learner seed. Freeze the budget
   and endpoint before collection; preserve all planned cases and keep reward,
   action-filter and optimizer-reset effects distinct. Do not promote whichever
   checkpoint happens to lead the development curve.
3. If success exposure remains limiting, add Act 1 late-act/boss continuations and
   successful public demonstrations from training cases. Include reward-screen
   completion and ordered selectors. Label assisted continuations explicitly and
   keep their outcomes separate from genuine-start Act 1 clear rate. Expand to
   later acts only after repeatable Act 1 improvement.

Configurable rewards now provide dense learning signal, and the guard prevents
updates when both advantages and value errors are absent. The remaining
completion failures and Act 1 learning goal motivate the next experiment.
Keep canonical run victory distinct from Act 1 task success, preserve checkpoint
lineage, and retain every planned cutoff and defeat in follow-up comparisons.

Repeatability is scoped to recorded software, hardware and deterministic settings;
[PyTorch documents limits across versions and platforms](https://docs.pytorch.org/docs/2.14/notes/randomness.html).
Do not promise bitwise equivalence across devices or unsupported resume points.
Implementation completion and improved gameplay are separate results, and both
must be reported honestly.
