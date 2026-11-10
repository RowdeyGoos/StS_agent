# Representation screen on combat-search targets — 2026-10-22

Status: **complete; no representation qualified under the registered rule.**

Candidates were fitted to the search targets from the
[distillation study](COMBAT_SEARCH_DISTILLATION_2026_10_18.md) and measured on
held-out campaigns. The specialist's own combat-graph representation fitted
them best. Neither a 128-wide version of it nor the feature study's flat,
pooled or compact designs did better. The wider model fitted its training data
better without generalizing better, so the limit is generalization from these
labels, not the representation or its capacity. No default changed.

## Result

Held-out fit at epoch 16 (11,770 decisions from 156 held-out campaigns; mean of
three seeds, seed range in brackets). KL is the target-weighted log-ratio of
the search distribution to the candidate's, in nats; lower is better.
Override agreement counts decisions where the target's top action differs from
the specialist prior's, i.e. where search changed the choice.

| Candidate | Params | Held-out KL | Top-action agreement | Override agreement | Fit KL |
| --- | ---: | ---: | ---: | ---: | ---: |
| Specialist prior, untrained (reference) | — | 0.308 | 80.8% | 0% | — |
| **Specialist, distilled (warm)** | 223k | **0.265** [0.264–0.265] | **79.1%** | 15.3% | 0.203 |
| Combat graph 48, fresh (control) | 223k | 0.278 [0.275–0.281] | 77.8% | 15.6% | 0.219 |
| Combat graph 128, fresh | 850k | 0.278 [0.276–0.279] | 78.0% | 17.1% | 0.192 |
| Rich compact pooling 64 | 98k | 0.330 [0.327–0.336] | 75.6% | 17.3% | 0.296 |
| Original rich pooling 64 | 144k | 0.339 [0.335–0.342] | 75.1% | 18.5% | 0.306 |
| Basic flat with identities 64 | 2.5M | 0.418 [0.411–0.424] | 71.9% | 19.0% | 0.258 |

| Candidate − combat graph 48 (fresh) | Held-out KL, 95% | Top agreement, 95% |
| --- | --- | --- |
| Specialist, distilled | −0.014 [−0.019, −0.010] | +1.3 points [+0.8, +1.8] |
| Combat graph 128 | −0.001 [−0.004, +0.003] | +0.2 [−0.2, +0.5] |
| Rich compact pooling | +0.052 [+0.043, +0.061] | −2.3 [−3.1, −1.6] |
| Original rich pooling | +0.060 [+0.050, +0.071] | −2.7 [−3.6, −2.0] |
| Basic flat with identities | +0.139 [+0.127, +0.152] | −6.0 [−6.7, −5.2] |

Intervals come from 2,000 bootstrap resamples of held-out campaigns, paired on
identical decisions.

- **Decision rule.** A representation qualified for RL confirmation if its
  held-out KL was below the fresh combat graph's with the interval excluding zero,
  and it followed more overrides. None qualified. The distilled specialist is a
  reference, not a candidate: its advantage comes from prior RL training, not
  its architecture.
- **Capacity is not the limit.** Width 128 fit its training campaigns better than
  width 48 (0.192 vs 0.219) but generalized identically. Fresh combat graphs fit
  training campaigns 0.06–0.09 nats better than held-out ones.
- **The combat graph learns these targets fastest.** From scratch it passed the
  specialist prior by epoch 4 (0.292, width 48). The study designs were still
  above 0.36 at epoch 8.
  - Compact and original pooling generalized (fit ≈ held-out) but were still
    improving at epoch 16.
  - Basic flat overfit: its held-out KL was lowest at epoch 8 (0.409).
  - Within the study family, compact pooling was slightly better than original
    pooling. The 6.7× smaller compact rollout storage therefore costs nothing here.
- **Distillation saturates after one epoch.** The warm specialist's held-out KL
  was 0.262 after epoch 1 and 0.265 after epoch 16, while its fit kept
  improving. This matches step 3, where 1, 4 and 16 epochs gave similar greedy gains.
- **Overrides remain hard.** Every candidate followed only 15–19% of search's
  held-out overrides. Gaining overrides costs agreement elsewhere: every trained
  model's overall agreement fell below the untrained prior's 80.8%.
- **The gap is mostly not target noise.** Target noise accounts for roughly 0.06
  nats at openings, while the best held-out KL is 0.265.

## Design

The protocol and config (`runs/combat-screen-20261022/protocol.json`,
`config.json`, SHA-256 `ee7eaf23…`) were frozen before any encoding or training.

- **Data:** all 60,738 searched decisions from the step-3 collection: 3,072
  training elite and boss fights, teacher `combat_belief_v1` at 24 simulations.
  - Campaigns were assigned by sha256(salt:campaign), 20% held out, so a
    campaign's decisions never cross: 48,968 fit and 11,770 held-out decisions.
  - Content identities for the flat candidate came from fit campaigns only (303 names).
- **Recipe:** one shared recipe mirroring `search-distill`: Adam at learning rate
  3e-4, batch 32, 16 epochs, soft cross-entropy plus 0.25 × the completed-return
  value loss, and gradient clipping at 1.0. Seeds 101/202/303 set initialization
  and batch order; the warm reference varies only in batch order.
- **Inputs:**
  - Production candidates use the detached planning view.
  - Study candidates use their own raw-view encoders, entity capacity 128, and
    public history replayed from each fight's anchor and reveal receipts, as in
    live play.
  - The held-out decision index was verified identical across all six candidates.
- **New tooling:** `sts-agent-train search-screen` (`game/agent/training/search_screen.py`).
  It encodes once per distinct encoder and fits every seed. `--report` pairs
  candidates on the shared held-out index.

### Fixes made for the screen

- **Study history rejected fresh adapters.** `PublicHistory.restore` compares an
  anchor's opening with the current public start. It rejected 431 of the 3,072
  collected fights. The cause was the equal-copies naming issue fixed for search
  in the [search benchmark record](COMBAT_SEARCH_BENCHMARK_2026_10_17.md): the
  recording owner and a fresh adapter list a lone enchanted copy at different
  positions. The endpoint comparison now orders deck copies by public content.
  This also matters for benchmark evaluation of any study model.
- **Fresh production candidates ignored their seed.** The first launch passed
  the seed to the global RNG, which `ActorCritic` then reseeded with its own
  default. The independent review caught this before any result was used. The
  runs were restarted from scratch with the fix and a test that checks initial
  weights differ by seed.
- The independent review otherwise confirmed the target alignment, loss,
  returns, split, bootstrap, encoder sharing and warm conversion.

Elapsed times:
- Encoding: 12–20 minutes per distinct encoder.
- Wall time: 1 h 37 min from 13:30 to 15:07, running five processes with three
  threads each.
- Training: study candidates took 30–36 minutes each including encoding. The
  warm specialist and graph-48 shared one 91-minute process (one encoding, six
  fits); graph-128 took 97 minutes.
- Independent review: 10 minutes.
- User wait: none.

Report `runs/combat-screen-20261022/screen.json`, SHA-256 `22b42dcf…`; build
`439abbab…` (uncommitted, on `7e975686`).

## Interpretation and next step

Fresh combat graphs at either width, and the warm specialist, sit 0.27–0.28
nats from the targets on new campaigns. Their training fit is already much
closer. A representation change would not help at this scale, but more or
better labels might. Two measurements would separate those:
- **Data scaling.** Refit on 25%, 50% and 100% of the fit campaigns. If held-out
  KL keeps falling with data, more collection rounds are the lever.
- **Target quality.** Label a sample of decisions with more simulations. If
  targets agree more across repeats and the network fits them better, the 24-simulation targets limit learning.

Meanwhile, search at play time already provides the +6.8 / +6.7 point gain;
an Act 1 campaign check with search enabled would show what it is worth to clear rate.

## Limits

- One teacher, one dataset and one recipe; no per-architecture tuning.
- Held-out campaigns come from the training population, not the validation
  benchmark. Supervised fit is not play strength.
- Fresh candidates learn only from these labels, while the warm reference had RL
  pretraining. Width and design are confounded in the study family; their widths
  follow the roadmap baselines.
