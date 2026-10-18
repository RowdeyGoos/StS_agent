# Hidden-state resampling for combat PPO — 2026-10-17

Status: **complete; not adopted.** Resampling the hidden state of training starts
made no difference to elite or boss play at this data scale. Neither arm improved
bosses over its initializer; both gained about 2 points on elites. No default
changed. This is step 2 of the user-requested combat-first plan, measured on the
[boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md).

## Question and design

Corpus PPO restores frozen snapshots, so every visit to a fight replays the same
draw order and RNG. The 1M-decision Vantom specialist rose from 50 to 76 of 101
training fights while validation stayed flat, consistent with memorizing those
realizations. The question was whether redrawing hidden state on every restore
improves elite and boss play.

The protocol (`runs/combat-step2-20261017/protocol.json`) was frozen before any
step-2 training:

- **Initializer:** the Vantom specialist 250k, forked into the full catalog
  vocabulary (564 → 3,185 names, 222,866 parameters). New embeddings copy its old
  unknown row, so initial logits were asserted equal to the specialist's. Its value
  head was refitted for 400 updates on 3,967 Monte Carlo targets from 4,096 TRAIN
  decisions (held-out MSE 0.205 → 0.180).
- **Arms:** `frozen` (current behavior) and `resampled` (new
  `"hidden_state": "resampled_v1"`). Everything else is shared: corpus, equal
  room-kind schedule, PPO v2 corpus preset with learning rate 1e-4 and entropy
  1e-3, and per seed the same learner seed and episode cursor.
- **Budget:** three seeds per arm × 15 exact-resume chunks of 16,384 = 245,760
  decisions per learner, with no checkpoint selection.
- **Endpoint:** equal-weight boss win rate at the final chunk, averaging the three
  seeds per arm, with a 95% campaign bootstrap shared by all learners. Adoption
  required an interval excluding zero and an elite decline of at most 2 points.

## Implementation

- `game/headless/run/hidden.py` permutes the draw pile uniformly (cards with
  Imbued or Perfect Fit keep their positions) and advances each bound combat RNG
  stream by 1–1,024 ordinary draws, keeping its owning seed. Public observations
  are unchanged and the state snapshots and restores normally.
- `PPOExperiment.hidden_state` binds the treatment to the experiment identity.
  Frozen experiments omit it, keeping all historical identities (13 existing
  experiment files compared byte for byte). `CorpusEnvironment` applies resampling
  after the verified restore, seeded from the reset seed through a separate
  SHA-256 domain, so replay audits reproduce episodes. `validate_factory` rejects
  a mismatched or missing factory, including on exact resume.
- **Engine fix found while building the training corpus:** potions claimed or
  discarded through relic pickups inside a scripted event were missing from the
  event's potion history. Tiny Mailbox rest rewards during Dense Vegetation,
  followed by a discard, then failed event validation when its fight started.
  `relics/pickup.py` now records those changes. `events/potion_context.py`
  ignores refused, no-change acquisitions (for example under Sozu), which the
  review showed the first version recorded incorrectly.

An independent review of the resampling found no blocking issue. It restored
1,200 real openings and resampled 2,400 openings and 6,252 continuations: no
public-state change, restore failure, unchanged state or play error. A second
review of the engine fix found the Sozu case, now covered by a regression test.

## Corpora

| Corpus | Settings | Result |
| --- | --- | --- |
| Benchmark | Rebuilt with the 2026-10-17 settings after the source changes | All 1,728 elite/boss openings identical to the original |
| Training | 512 fresh campaigns per region, start index 32,000,000, mixed elite routes, turns 1–12, no planning receipts | 8,335 fights / 30,908 starts; 539 boss fights (70–116 per boss), 1,127 elite fights; built in 311 s |

Only 26 training starts (of 603 Waterfall Giant starts) were in the Giant's
eruption phase, so explosion practice was sparse.

## Results

All six learners trained 1,474,560 decisions with no skipped updates or failed
episodes. Each 245,760-decision learner took about 22.5 minutes of PPO.

| Decisions | Bosses, frozen | Bosses, resampled | Resampled − frozen | Elites, frozen | Elites, resampled | Resampled − frozen |
| ---: | ---: | ---: | --- | ---: | ---: | --- |
| 0 (initializer) | 48.7% | 48.7% | — | 79.1% | 79.1% | — |
| 81,920 | 48.3% | 48.7% | +0.3 [−1.2, +1.9] | 79.7% | 80.0% | +0.3 [−0.5, +1.1] |
| 163,840 | 48.6% | 49.5% | +0.9 [−0.7, +2.5] | 80.2% | 80.6% | +0.4 [−0.5, +1.3] |
| 245,760 | 48.9% | 48.2% | **−0.7 [−2.1, +0.8]** | 81.1% | 80.8% | −0.3 [−1.1, +0.5] |

At the endpoint, the arms against the initializer were frozen +0.2 [−1.9, +2.4]
and resampled −0.5 [−2.6, +1.6] on bosses, and frozen +2.0 [+0.7, +3.2] and
resampled +1.7 [+0.5, +2.9] on elites. Per-seed boss differences were −2.7, +1.8
and −1.2.

Per-boss changes were small and mixed. The Kin (48% → 50–57%) and Lagavulin
Matriarch (28% → 26–34%) rose slightly, while Vantom (55% → 48–54%) and
Ceremonial Beast slipped, and the Waterfall Giant did not improve (20 wins of 87
for the initializer, 15–19 for the learners). The Vantom-specific edge appears
diluted by the general mix.

**No memorization occurred in either arm.** Training-time boss win rates under
the sampled policy stayed at 38–41% from the first three chunks to the last three,
in both arms. Each learner played about 5,700 boss episodes (about 950 per boss)
over 539 boss fights, about 10.5 visits per fight including later-turn starts. The
1M Vantom specialist made roughly 460 visits to each of its 101 fights (about
46,900 episodes). Resampling removes a memorization channel that this data scale
never used.

## Interpretation

- **Resampling is unnecessary at this data scale.** Keep frozen starts as the
  default. Revisit resampling for small corpora trained for many epochs, which is
  the regime where the Vantom specialist overfit; this study does not test that.
- **PPO barely moves bosses from this initializer.** 245,760 decisions with a
  third of episodes on bosses gave about 950 episodes per boss and no boss gain.
  Elites improved modestly. The specialist's own Vantom gains came from roughly
  11,700 Vantom episodes in its 250k PPO (estimated from its continuation's
  episode rate), so per-boss practice volume is a
  plausible limit, not an established one.
- **The more promising boss levers** remain the ones with measured effects:
  search (+14–19 points over network-only for search students on Vantom) and
  imitation of successful hard fights (+3–5 boss points). Boss-only or much longer
  PPO is a costlier alternative.

## Limits

- One initializer, one hyperparameter setting, three seeds and a 245,760-decision
  budget; larger budgets or boss-only sampling could behave differently.
- The benchmark is a reused validation panel with greedy play on frozen starts.
- Explosion practice for the Giant was too rare to test that idea.

## Timing and artifacts

Corpus collection 341 s (benchmark) + 311 s (training); initialization 131 s;
training 8,824 s; final evaluation 918 s; the two curve evaluations about 14
minutes each. A first launch stopped at the engine fault and a second at a
private-directory permission error in the experiment script; both were fixed
before the reported run. Implementation and review time were not instrumented.

Artifacts are in `runs/combat-step2-20261017/`: `protocol.json`,
`initialization.json`, `training.json`, `analysis-*.json` and the evaluation
reports. Final report SHA-256
`0b4d9acfca0c5ffb1f65b0dbc910e21f0711a143199b79af097526e2ea5967f9`; implementation
build `9e4b7f6ed989…`.
