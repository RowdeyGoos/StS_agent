# Minibatch 64 for corpus PPO — 2026-10-18

Status: **complete; the registered rule recommends minibatch 64 at learning rate
1e-4.** The generated corpus PPO preset (`combat-ppo.json`) now uses minibatch 64.
Its learning rate is unchanged, and fine-tuning runs keep their 1e-4 override. A
[follow-up](#follow-up-learning-rate-2e-4) found that doubling the learning rate
does not help.

With minibatch 64, corpus PPO trained **12.5% faster** than with minibatch 16;
updates alone were 22% faster. It was not worse on the
[boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md):

| Endpoint | Minibatch 64 − 16 | 95% interval |
| --- | ---: | --- |
| Bosses | +1.7 points | +0.2 to +3.3 |
| Elites | −0.3 points | −1.2 to +0.6 |

Non-inferiority and speed are the robust findings. The boss gain is tentative:
- its interval barely excludes zero;
- an identical-recipe minibatch-16 arm from step 2 scored 1.0 point above this
  study's minibatch-16 arm, so replicate variation is about as large as the
  effect.

## Question and design

After the [training-speed work](TRAINING_SPEED_2026_10_18.md), updates are about
60% of PPO wall time. Per decision, a training step costs 0.71 ms at minibatch 16
and 0.52 ms at minibatch 64. In the [Vantom PPO calibration](VANTOM_SHARED_PPO_2026_10_15.md),
minibatch 64 was the strongest alternative recipe, but its intervals included
zero.

The protocol (`runs/combat-batch64-20261018/protocol.json`) was frozen before
any corpus build, training or evaluation. Its design repeats the
[step-2 study](COMBAT_HIDDEN_STATE_2026_10_17.md) exactly, except for the
minibatch:

- **Initializer:** the step-2 weights, unchanged (SHA-256 `a6a0dac3…`), with a
  fresh optimizer for each learner.
- **Arms:** `b16` is step 2's frozen recipe. `b64` differs only in
  `ppo.batch_size = 64`. Both use learning rate 1e-4, entropy 1e-3, rollout
  4,096, two epochs and target KL 0.03. With minibatch 64 a learner takes 4×
  fewer optimizer steps.
  - `initialize.py` asserted that `b16` equals step 2's frozen experiment apart
    from the rebuilt corpus identity.
- **Corpora:** both were rebuilt for the current code with the step-2 commands.
  The benchmark reproduced all 1,728 original elite and boss openings.
- **Seeds:** the three step-2 learner seeds and episode cursors. Within each
  seed, both arms see the same sequence of training starts.
- **Budget:** 15 chunks of 16,384, so 245,760 decisions per learner, with no
  checkpoint selection.
- **Endpoints:** equal-weight boss and elite win rates at the final chunk, as
  three-seed means per arm. The difference uses a 95% source-campaign bootstrap
  shared by all learners. The second endpoint is training wall time per
  learner.
- **Decision rule:** recommend minibatch 64 if either
  (a) its boss or elite interval lies above zero and neither falls by more than
  2 points, or
  (b) both lower bounds are at or above −2 points and it trains at least 10%
  faster.

  Both conditions hold.

## Results

All six learners trained 245,760 decisions with no failed chunk and no KL early
stop.

| Per learner, mean of three seeds | Minibatch 16 | Minibatch 64 |
| --- | ---: | ---: |
| PPO wall time | 909 s | 796 s |
| — collection | 375 s | 374 s |
| — updates | 516 s | 403 s |
| Decisions per second | 270 | 309 |
| Optimizer steps | 30,720 | 7,680 |

Seed-to-seed spread in wall time was at most 6 s.

| Decisions | Bosses, b16 / b64 | b64 − b16 | Elites, b16 / b64 | b64 − b16 |
| ---: | ---: | --- | ---: | --- |
| 0 (initializer) | 48.7% / 48.7% | — | 79.1% / 79.1% | — |
| 81,920 | 49.2% / 48.4% | −0.8 [−2.1, +0.6] | 80.3% / 80.5% | +0.2 [−0.5, +0.9] |
| 163,840 | 47.9% / 48.2% | +0.2 [−1.4, +2.0] | 80.7% / 80.5% | −0.1 [−1.0, +0.8] |
| 245,760 | 47.9% / 49.6% | **+1.7 [+0.2, +3.3]** | 81.0% / 80.7% | −0.3 [−1.2, +0.6] |

- **Per seed**, the final boss differences were +2.0, +1.0 and +2.1 points;
  each interval individually includes zero. The elite differences were −0.8,
  −0.1 and +0.1.
- **Against the initializer**, at the endpoint:

  | Arm | Bosses | Elites |
  | --- | --- | --- |
  | b16 | −0.7 [−3.0, +1.4] | +1.8 [+0.5, +3.1] |
  | b64 | +1.0 [−1.1, +3.0] | +1.6 [+0.4, +2.8] |

  Neither arm significantly improved bosses.
- **Per boss**, b64 minus b16:

  | Boss | b16 | b64 | Difference |
  | --- | ---: | ---: | ---: |
  | Lagavulin Matriarch | 23.9% | 29.8% | +5.9 |
  | The Kin | 51.3% | 54.0% | +2.7 |
  | Ceremonial Beast | 76.0% | 77.7% | +1.7 |
  | Waterfall Giant | 19.9% | 21.5% | +1.5 |
  | Soul Fysh | 62.5% | 63.2% | +0.7 |
  | Vantom | 53.9% | 51.7% | −2.2 |
- **Replicate.** Step 2's frozen arm used the same recipe as b16 but a separately
  built corpus, and so a different case order. It scored 48.9% on bosses (seeds
  49.6, 47.5 and 49.6) and 81.1% on elites. Against that replicate, b64 is +0.7
  points on bosses.

## Interpretation

- **Use minibatch 64 for this corpus fine-tuning recipe.** It is at least as good
  and saves about one eighth of PPO time.
  - The saving comes entirely from updates: fewer, larger optimizer steps
    amortize the fixed per-step cost.
  - Collection is unchanged.
- **Treat the boss gain as unconfirmed.** The bootstrap covers benchmark
  campaigns, not training randomness. Two runs of the identical 16 recipe
  differed by 1.0 point.
- **The curve fits the step count.** b64 was slightly behind at 81,920
  decisions, level at 163,840 and ahead at the end. With a quarter of the
  optimizer steps, it may learn more slowly early on at the same learning rate.

## Follow-up: learning rate 2e-4

With minibatch 64 at learning rate 1e-4, the policy moves 2.6× less per update
round than with minibatch 16. A single-round measurement on the saved production
rollout gave a full-rollout KL of 0.0041 versus 0.0107. Learning rate 2e-4
restores about the same movement (0.0091). The follow-up asked whether that
extra movement learns better.

- **Protocol.** `runs/combat-minibatch64-lr-20261018/protocol.json` was frozen
  before training.
  - One new arm, `b64lr2`, is the parent's b64 recipe with
    `ppo.learning_rate = 2e-4`.
  - It uses the parent's corpora, initializer weights, seeds and episode
    cursors, so it pairs with the parent's learners.
  - The rule was to adopt 2e-4 only if, against b64 at 1e-4, its boss or elite
    interval lay above zero without a fall of more than 2 points on the other.
- **Merge check.** Only the new learners were evaluated, with the parent's b64-s1
  and both baselines alongside. At every stage those reproduced all 1,728
  parent outcomes exactly, so the reports were merged. The analysis also
  reproduces the parent's intervals.

| Decisions | Bosses, b64 / b64lr2 | b64lr2 − b64 | Elites, b64 / b64lr2 | b64lr2 − b64 |
| ---: | ---: | --- | ---: | --- |
| 81,920 | 48.4% / 47.1% | −1.3 [−2.7, +0.0] | 80.5% / 79.7% | −0.8 [−1.5, −0.0] |
| 163,840 | 48.2% / 49.2% | +1.0 [−0.4, +2.4] | 80.5% / 80.7% | +0.1 [−0.6, +0.9] |
| 245,760 | 49.6% / 48.5% | **−1.1 [−2.5, +0.3]** | 80.7% / 80.8% | +0.1 [−0.7, +1.0] |

- **At the endpoint**, against minibatch 16 at 1e-4: bosses +0.6 [−0.9, +2.1]
  and elites −0.1 [−1.0, +0.8].
- **Per seed**, the boss differences against b64 were −0.8, −2.0 and −0.5. The
  elite differences were +1.1, −1.2 and +0.5.
- **Against the initializer**, b64lr2 scored bosses −0.1 [−2.4, +2.1] and
  elites +1.7 [+0.6, +2.8].
- **Speed** was unchanged: 794 s per learner versus 796 s, with no KL early
  stops.

The rule keeps 1e-4. Restoring minibatch 16's per-round movement did not improve
learning; minibatch 64 at 1e-4 did at least as well with less movement. All three
recipes ended within about 2 points of each other. Each gained 1.6–1.8 elite
points over the initializer and none improved bosses, so these knobs barely
matter for PPO from this initializer.

The follow-up was requested at 11:29 UTC and its pipeline ran from 11:32:51 to
12:36:26:

| Stage | Time |
| --- | ---: |
| Training, three learners | 2,750 s |
| Evaluations | 354 s, 350 s and 350 s |

Its final report SHA-256 is
`47fb34558ca7f4382d8de843198bd7ac84611a0fbed2b442f48e904bdd3d9366`.

## Limits

- One initializer. Learning rates 1e-4 and 2e-4 were tested at minibatch 64.
- The generated corpus preset uses learning rate 3e-4 and entropy 0.01. This
  study does not directly measure minibatch 64 at those settings. The Vantom
  calibration did, and found it promising but unresolved.
- Three seeds, and the validation panel reused from steps 1 and 2; there is no
  held-out claim.
- PPO barely moves bosses from this initializer, leaving little room for a
  boss difference.

## Timing and artifacts

The request came at 08:44 UTC and the pipeline ran from 08:49:49 to 11:00:03 UTC
(2 h 10 min):

| Stage | Time |
| --- | ---: |
| Both corpora | 6 min 51 s |
| Initialization | 13 s |
| Training, six learners | 5,872 s |
| Final evaluation | 548 s |
| Curve evaluations | 483 s and 484 s |

Setup took about 5 minutes. User wait: none.

Artifacts are in `runs/combat-batch64-20261018/` (git-ignored, 21 GB with
recordings): `protocol.json`, `initialization.json`, `training.json`,
`speed.json`, `analysis-*.json` and the evaluation reports.
- Final report SHA-256: `d35eb72bd9773a4530d656f0024d739f112579d07d991af72a9f44372698da1b`.
- Protocol SHA-256: `f13331375f00158049d35dabf28ccef6b895ca1072b9e5ae5c98a8fe9e0815c4`.
