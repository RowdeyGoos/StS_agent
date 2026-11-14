# Noncombat policy proposal — 2026-11-14

Status: **proposal**. Research and design only: no training, no evaluation run
and no source change. The findings come from a single-process analysis of the
2,048 recorded campaigns of the [Act 1 record](evidence/ACT1_SEARCH_2026_11_13.md).
Those are validation campaigns: they are analysed here and must never become
training data.

Every claim carries a label: **(M)** measured here on those recordings, **(S)**
taken from a named source, **(H)** my hypothesis. Measured figures describe the
500k campaign policy's choices in the arm with 24-simulation search (512
campaigns) unless stated. They are descriptive. The policy almost never tries
the alternatives, so none of them is the measured effect of a choice.

## Recommendation

1. **A transformer is not the next step.** In Act 1 the noncombat problem is
   small and short: about 28 real choices per campaign, 5 route branch points
   on a fully visible map, and a rest site before every boss (M). What the
   current policy lacks is a signal that says what each choice is worth with
   the frozen combat agent, not capacity or memory.
2. **Learn that value from paired forks.** Replay a training campaign, change
   one noncombat choice, let the same frozen players finish Act 1, and compare
   the two endings. Fit a small model that predicts the clear probability of
   every candidate and act on its best candidate. Repeat with the improved
   policy as the new base.
3. **Run two rule probes first.** They need no learning and minutes of
   compute: keep potions for the boss, and upgrade when a rest would heal
   almost nothing. The recordings suggest the first is the largest single
   leak, and it sits in the combat agent, not in the noncombat policy.
4. **First experiment that can show the idea is wrong:** a replay-fork pilot
   of 24,000 paired labels, about 2.4 hours on 16 cores, built on the existing
   runner. Its threshold is in the [plan](#staged-plan).

## What the recorded campaigns show

All rows are (M).

| Choice | What the campaign policy does | Reading |
| --- | --- | --- |
| Rest sites | Rests at all 1,473 (2.9 per campaign) and never upgrades. Its probability of upgrading averages 0.13% over 168 sampled sites. 165 rests (11%) heal nothing and 253 (17%) heal at most 5 HP | 0.3 to 0.5 free upgrades per campaign are forgone. Elsewhere resting looks right for Act 1 (below) |
| Potions | Collects 4.1 per campaign and buys 0.7. The combat agent uses every potion in its next fight: of 1,665 won normal fights entered with a potion, 1,661 end with none. 3.6 per campaign go to normal fights, which are won 99.4% of the time; 0.56 reach the boss | The largest visible leak. It is decided inside combat, where search values a win at 1 plus a tenth of the HP kept and a potion costs nothing |
| Gold and shops | Takes the shop in 142 of 286 branches that offer one. In 345 visits it buys 343 potions, 319 cards and 6 relics and never removes a card. It reaches the boss with 104 gold on average; 26% of campaigns hold 150 or more | Gold left at the boss is worth nothing for Act 1 |
| Card rewards | Takes a card on 87% of 4,947 screens. Picks direct-damage attacks (Anger 383 of 386, Molten Fist 345 of 374) and almost never block, draw or power cards (Armaments 0 of 436, Blood Wall 0 of 454, Shrug It Off 2 of 439, Offering 0 of 71, Demon Form 0 of 83). Boss decks hold 14.5 attacks, 0.95 added skills and 0.42 powers in 20.1 cards | Value unknown. The combat network was trained on exactly these decks |
| Elites | Chooses the elite in 9 of 466 branches that offer one. Its 0.51 elite fights per campaign are nearly all forced. A won elite costs 23.7 HP and 9.5% are lost | Not clearly a mistake for Act 1 alone (H) |
| Routes | 5.0 real branch points per campaign. Chooses the rest site in 512 of 559 branches and prefers combat rooms to unknown rooms: 8.0 and 1.7 per campaign that reaches the boss, against 6.0 and 3.7 for the heuristic | More fights give more card rewards, and more training reward (below) |
| Size | 64.9 noncombat decisions per campaign: 8 are forced, about 28 are reward navigation and about 28 are real choices | |

**What separates boss wins from losses.** A logistic regression over all 1,597
boss fights of the four players, with the boss, search and who chose as
covariates, gives per unit (M, descriptive; intervals from a bootstrap over
starts):

| Carried into the boss fight | Log-odds of winning | In the same units |
| --- | ---: | --- |
| 10% of maximum HP | +0.73 [+0.65, +0.85] | |
| One potion | +0.85 [+0.64, +1.11] | about 12% HP |
| One relic | +0.34 [+0.19, +0.52] | about 5% HP |
| One upgraded card | +0.30 [+0.18, +0.43] | about 4% HP |
| One power card | +0.36 [+0.15, +0.60] | about 5% HP |

- The potion figure is close to a natural experiment, because a potion held at
  the boss is almost always one that dropped after the last fight. Bosses
  entered with no potion are won 47.6% of the time (233), with one 63.0% (200)
  and with two or three 22 of 25, at the same entry HP (88%), relics and deck
  size: +15.4 points [+5.8, +24.6] for the first potion (M).
- In won normal fights the player loses 8.4 HP with no potion and 5.5 with one
  (M, unmatched). A potion is thus worth about 3 HP in a normal fight and about
  three times that at the boss (H).
- Every campaign that reaches the boss passes a rest site on floor 15. HP is
  67% before it and 88% after (M). HP saved earlier is partly capped there,
  which is why resting everywhere costs little and an upgrade is free only when
  the rest would heal nothing.
- Card and relic identities add nothing at this sample size: predicting the
  boss outcome reaches AUC 0.793 from HP and boss, 0.828 with the counts above
  and 0.818 with identities added (M, five folds grouped by start).
- One fight is mostly noise: deck, relic and HP summaries predict the HP lost
  in a normal fight with a mean error of 5.5 HP (R² 0.31) and in an elite with
  11.3 HP (R² 0.21) (M).

**Why the policy behaves this way (H).** It was trained to play everything with
+0.2 per fight won and +0.1 times the HP fraction kept, against +1 for the act
(S: [training guide](AGENT_TRAINING.md#increased-reward-continuation-to-500k-decisions-2026-09-30)).
A campaign wins 9.0 fights (M), so fights pay about 2.5 and clearing pays 1.
That rewards many easy fights, high HP and no risk, which is what it does. Its
last 400k decisions were 2,892 training episodes (S), roughly fifty times fewer
than one training leg of the external project below.

**Three consequences.**
- For Act 1 alone the policy's caution is mostly rational. The behaviour that
  looks odd (rest always, few elites) follows from a 16-floor horizon with a
  healing floor before the boss. It would be poor play in a three-act run.
- The value it leaves is in resources that are never tried or never priced:
  potions, gold, card removal, free upgrades and possibly its card choices.
- The recordings cannot rank these. Only interventions can, because the policy
  gives 0.13% to upgrading, 0.9% to removal and 1.7% to an optional elite (M).

## Options compared

Gains are (H) in Act 1 clear points; costs use the measured 5.2 s per campaign
without search and 126 s with it (M).

| Option | Expected gain | Compute, 16 cores | Agent work | Main risk | Verdict |
| --- | --- | --- | --- | --- | --- |
| Rules on the current policy: keep potions for the boss; upgrade when a rest heals at most 5 HP | Potions +5 to +15; upgrades +1 to +3 | 3 minutes per arm without search | Small | Correlational basis; the potion rule changes the combat action filter | **Do first** (stage 0) |
| (a) PPO on noncombat decisions, combat frozen and played by the network | +5 to +15 after 100k campaigns or more, by analogy with +3 to +16 per training leg elsewhere (S) | 150k campaigns: 13.5 h | Medium: an environment in which the frozen network plays the fights; reward is the act clear only | On-policy exploration from this checkpoint almost never tries the neglected actions; its curve here was non-monotonic (S) | Second learner if forks stall |
| (b) Fight-outcome model in place of the fights | — | Cheap | Medium | Failed elsewhere in closed loop: runs became 2.3 times too survivable while per-fight error looked fine (S). Here most of a fight's HP loss is noise (M) | Reject as a simulator; keep for the boss fight only (stage 4) |
| (c) Search over the visible map with that model | Small alone | Trivial: 5 branch points | Small | Inherits the bias of (b) | Fold in as route features |
| (d) Paired forks from saved states, a value per candidate, greedy improvement | +3 to +8 per round | 100k labels: 5.6 h | Medium to large: fork collector, value fit, export | New collector; improves one step per round | **Recommend** |
| (e) Sequence model over the run history | None expected | — | Large | The public decision already holds the whole state; return-conditioned sequence models fail under chance (S) | Reject |

## Is a transformer warranted

Not now, and not for long-term planning.

- **There is little to plan in Act 1.** Five branch points on a visible map,
  a forced rest before the boss and about 28 real choices (M). A route's
  consequences can be enumerated exactly; they do not need to be remembered.
- **History adds almost nothing.** The public decision carries the deck,
  relics, potions, HP, gold, the whole map with visited nodes and a history
  node ([contract](../game/agent/contracts/full.py)). A model over past
  decisions would re-derive what is already in the state.
- **The evidence favours small models.** A 100k-parameter MLP trained on 15k
  games improved a noncombat policy (S: sts-rl-agent). A larger card-pick model
  with learned identities was the most accurate offline and the worst in play
  (S: Singer). In this project attention and wider networks have not beaten
  the graph for combat (S: [overview](COMBAT_OVERVIEW.md#network-architecture-and-features)).
  The one strong system with a run-level transformer trained it on 144,000
  games per leg (S: spire-mentor); nothing I read isolates the architecture.
- **The current graph does have two real limits** (S: [model](../game/agent/training/model.py)).
  It passes messages twice, so a map candidate sees two rows ahead of a 15-row
  route. And a candidate card meets the deck only through one mean-pooled
  48-number state.
- **Where attention is the right tool:** a candidate card, upgrade or removal
  attending over the deck and relic tokens, to value a card given the deck. It
  buys synergy-dependent values. At 100k labels a common card's average value
  is known to about ±5 points (H), so synergies are out of reach for now. The
  route limit is cheaper to fix with derived route features than with depth.

The question is settled cheaply once labels exist: screen the variants offline
on held-out labels, as the [decisions](../DECISIONS.md) already prescribe for
representations (stage 2).

## Recommended approach

**What is learned.** One function: the probability of clearing Act 1 if a
candidate is taken at a public noncombat decision and the base players finish
the act. The base players are the current campaign policy for noncombat choices
and the frozen combat network for fights.

**Labels: paired forks.** From a training-split start, play the base campaign.
Then, for 8 of its real choices, play it again from the same seed with one
change: at that decision take a uniformly random other candidate, and follow
the base players before and after. Each replay gives one paired label, the
alternative's ending against the base ending. A change that opens a sub-choice
(upgrade, removal, shop) samples the sub-choice uniformly too. The pilot needs
only a wrapper policy around [`run_episode`](../game/agent/runner.py); the
paired evaluation already relies on same-seed replays staying identical until
the first different decision. Stage 4 replaces the replay with a restore of
the engine snapshot taken at the decision, which halves the cost.

**Network.** Start from the current graph network and its encoder, with the
candidate scorer trained as a value (sigmoid, cross-entropy on the endings) and
the embeddings initialised from the campaign checkpoint. Screen two additions
offline: route features per map candidate (over all paths to the boss: fewest
and most elites, rest sites and shops, rooms to the next rest site), and one
layer in which each candidate attends over deck and relic tokens (the existing
entity attention in `set_layers.py`).

**Acting.** Take the candidate with the highest predicted value. A policy
bundle already plays its highest-scoring candidate (S: `checkpoint.py`), so
the value network should export as an ordinary bundle that
`--noncombat-checkpoint` evaluates unchanged (H). If stage 3 shows switching
on noise, require a margin over the base choice.

**Rounds.** The improved policy becomes the base and the collection repeats.
One round improves single choices only; coordinated changes (take block cards
and also play them well) need several rounds, or PPO from the latest policy.

**Lower-variance labels (stage 4).** The boss fight is close to a coin flip
and ends 79% of the lost campaigns (S). Replace its result in a label with a
boss model's win probability given what is carried in, trained on boss fights
that the frozen agent plays with search from training campaigns. This is the
one use of a fight-outcome model: a single fight at the end, checkable against
real boss fights.

## Training signal and cost

| Item | Unit cost | On 16 cores |
| --- | --- | --- |
| Campaign, network plays the fights | 5.2 s, of which 2.1 s is recording (M) | 11,000 per hour |
| Campaign with 24-simulation search | 126 s (M) | 457 per hour |
| Boss fight with search | about 37 s: 32.7 searched decisions at 1.12 s (S: [search profile](evidence/SEARCH_PROFILE_2026_11_13.md)) | 1,570 per hour |
| Pilot: 3,000 base campaigns, 24,000 replays | 39 core-hours | 2.4 h |
| One round: 12,500 base campaigns, 100,000 snapshot forks at about 2.6 s (H) | 90 core-hours | 5.6 h |
| Boss model: 10,000 boss fights with search | 102 core-hours | 6.4 h |

- **The frozen combat agent stays affordable** because every label campaign
  uses the network without search. Search appears only in validation and in
  the boss model. Two results support this: the value of who makes the
  noncombat choices was the same without and with search, +24.6 and +23.0
  points (S: Act 1 record), and spire-mentor collects its training games at a
  quarter of its deployed search budget without a measured loss (S).
- **What the budgets resolve (H).** A paired label is −1, 0 or +1 with a
  standard deviation near 0.7. 24,000 labels resolve the best tenth of
  predicted switches to ±3 points. 100,000 resolve a choice family's mean to
  ±1 point and a common card to about ±5; the boss model should halve that.
- **Three rounds** cost about 17 hours of collection and 3 to 5 hours of
  validation.

## Prior work

External figures were read through automated page summaries and not checked
against the raw text.

| Source | What it did | What transfers |
| --- | --- | --- |
| [spire-mentor](https://github.com/tfriedel/spire-mentor) (StS2, Rust engine) | PPO trains a run-level transformer; MCTS without a network plays combat. 960 games per iteration for 150 iterations, collected at a quarter of the deployed simulations. Ironclad A0 wins 96.0% of full runs at 8,000 simulations. Paired gains per training leg of +3 to +16 points, one leg at −13 | The split into run policy and frozen search combat works at scale. Cheap combat during collection is acceptable. Its [surrogate study](https://github.com/tfriedel/spire-mentor/blob/main/docs/combat-surrogate-investigation.md) rejects a learned fight model inside training: per-fight error 0.071 looked fine while survival read 0.64 to 0.68 against 0.29. Lessons: check that every decision family is really reached and that embeddings receive gradient; judge by paired gates, not training win rate |
| [sts-rl-agent](https://huggingface.co/Jialeiv/sts-rl-agent) (StS1, sts_lightspeed) | A 100k-parameter MLP scores candidates for all noncombat choices, REINFORCE, 15k games; the simulator's MCTS plays combat. 6% to 14% wins on 50 seeds, no intervals | The same framing as option (a) with a tiny model. The gain came mainly from routing. Distilling the combat search into a network failed six times |
| [Oram](https://milesoram.github.io/slay-the-spire-ml-project.html) (StS1 replica) | Simulates each noncombat option and scores the result with a network that predicts the final floor, fed by a per-fight HP-loss predictor and path-permutation features. 4 wins in its best 100 runs | One value function for every choice type, and route features. Shops were its weak spot: purchases combine |
| [Slay-I](https://github.com/alexdriedger/SlayTheSpireFightPredictor) (StS1 mod) | Predicts damage taken per fight from 325,000 human fights, within about 7 HP; scores a card by damage saved | A fight predictor is a usable advisor. No effect on win rate is reported |
| [Singer, parts 3 and 11](https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a) (StS1) | Card-pick models from human runs. The most accurate (55.8%) played worst; a deck-to-win regression collapsed into a tier list. [Part 11](https://dev.to/doronsinger/part-11-pick-your-battles-d3p): elites are lost by choosing them with a deck that cannot kill fast | Imitation accuracy does not predict play. Correlational deck models overvalue what long runs contain, a warning for the regression above |
| [sts2Showcase](https://cmcour.github.io/sts2Showcase/) (StS2) | Seven PPO models, one per decision surface, trained one at a time; 250k runs; no win rate published | Its stated difficulty is that each model trains against stale versions of the others |
| [Vieira et al.](https://www.sbgames.org/proceedings2020/ComputacaoFull/209690.pdf), [Ward et al.](https://arxiv.org/abs/2009.00655) (card drafting) | RL draft agents for Legends of Code and Magic beat the best scripted drafters; networks imitate human Magic drafts best of four agents | Deck building as its own learned policy with a fixed player is established practice |
| [Tesauro and Galperin 1996](https://proceedings.neurips.cc/paper/1996/hash/996009f2374006606f4c0b0fda878af1-Abstract.html) | Monte-Carlo rollouts of a base policy per candidate cut backgammon error rates up to fivefold | The method behind paired forks: one-step improvement from rollouts of the base policy |
| [Paster et al. 2022](https://arxiv.org/abs/2205.15967) | Return-conditioned sequence models fail in stochastic environments | Against option (e) |

## Staged plan

Success is the paired Act 1 comparison. With search it uses 512 starts and
resolves 4 to 5 points; the marks are 42.8% without search and 50.6% with
(S). Without search a campaign costs 5 s, so 2,048 starts take 11 minutes per
arm and should resolve about 2.5 points (H). The registered gate is wider: its
radius is 12 points at 512 starts (S), so a gain of +5 clears it only from
about 3,000 starts, which take 16 minutes per arm without search and 6.5 hours
with it. The 512 recorded starts have now been analysed, so they are a
development panel; confirmation needs fresh validation starts.

| Stage | Work | Acceptance case | Cost |
| --- | --- | --- | --- |
| 0 | Two rule probes on the current players, no learning. (i) Potion use is not offered in normal fights while HP is above a floor. (ii) A rest that would heal at most 5 HP becomes an upgrade. Paired on the 512 development starts without search; the winner again with search | (i) At least 1.5 potions at the boss, and at least +5 points over 42.8% with an interval that excludes zero. If potions arrive and clears do not move, the reading of the recordings is wrong. (ii) Reported, not gated: its predicted +1 to +3 is below the resolution | 3 minutes per arm; 67 minutes per arm with search. Small change in the policy-action filter, with tests |
| 1 | **Replay-fork pilot.** Wrapper policy and a collection script on the existing runner. 3,000 training starts, 8 forks each | A replay without a change reproduces the base trajectory digest in 100 of 100 campaigns. A value model fitted on four fifths of the base campaigns is scored on the rest, over five folds: the tenth of forks it most prefers over the base choice must have a realized paired advantage of at least +3 points with an interval that excludes zero. Otherwise single choices hold no learnable gain at this size: stop and reconsider | 2.4 h; medium agent work |
| 2 | Offline screen on the pilot labels: graph, graph with route features, graph with candidate attention | A variant is adopted only if it lowers held-out loss with a paired interval that excludes zero | Minutes of CPU each |
| 3 | Export the greedy policy and validate it | At least +5 points over the base on 2,048 fresh validation starts without search, then at least +4 over 50.6% on 512 starts with search, each with an interval that excludes zero | 11 minutes per arm; 67 minutes per arm with search |
| 4 | Scale: snapshot forks, 100,000 labels per round, the boss model, two or three rounds | Each round at least +3 points over the previous policy on fresh starts without search; stop at the first round that fails | 5.6 h per round, 6.4 h once for the boss model |
| 5 | Later scopes: the same value as the exit value of combat search; a full-run objective | Separate decisions | — |

## Risks and what I could not determine

- **Nothing here is causal.** Every (M) figure is descriptive. The regression
  can overvalue what strong campaigns happen to carry, as Singer found.
- **The combat network knows only this policy's decks.** A policy that takes
  other cards hands it unfamiliar decks. Fork labels measure value with that
  network, which is the right target, but the best deck for it may not be the
  best deck for a better combat agent.
- **Labels without search, play with search.** The noncombat effect carried
  over once (S). It may not for cards that only search plays well.
- **Act 1 as the whole objective** rewards arriving healthy over growing
  stronger. A policy tuned to it will transfer badly to three acts.
- **Greedy choice on a noisy value picks noise.** Stage 1's threshold and a
  margin in stage 3 guard against it.
- **Replays and restores must be exact.** A recent fix concerned restored
  engines sharing state (S: commit `6171460e`). The identity check of stage 1,
  repeated for snapshot forks in stage 4, is the guard.
- **Not determined:** the effect of any single choice; whether the card
  preferences cost anything; what the starting relic choice is worth; how much
  HP a potion saves in a normal fight; variation between learner seeds; and
  whether stage 0's potion gain survives a combat agent that prices potions
  itself.

## Open questions for the user

1. **Objective.** Act 1 clear only, or also a value for what is carried into
   Act 2? The first is measurable today; the second avoids learning habits
   that the full run will punish.
2. **Potions.** May the combat agent's potion use be restricted for stage 0?
   The change is in the action filter, which the main session is working near.
3. **Base controller.** The roadmap keeps the noncombat heuristic fixed in
   hybrid checks. This plan needs the 500k campaign policy as the base.
4. **Privileged data.** Forks replay private seeds, and later restore engine
   snapshots, to label public choices. The labels are endings reached by public
   policies, like PPO returns, and I read that as allowed. It deserves a line
   in the decisions before stage 1.
5. **Panels and cores.** A fresh validation panel of 2,048 starts, and about
   8 hours of 16 cores for stages 0 to 3, which compete with the search-speed
   benchmarks.

## Suggested edits elsewhere (not made)

- [Documentation index](README.md): link this proposal.
- [Roadmap](../ROADMAP.md): add the noncombat thread under item 3 and, if
  question 3 is approved, replace the fixed-heuristic constraint.
- [Combat overview](COMBAT_OVERVIEW.md#what-is-not-known), question 4: add that
  the combat agent spends every potion in its next fight and that a potion
  held at the boss goes with +15 points [+6, +25] of boss wins.
- [Decisions](../DECISIONS.md): if adopted, record that the noncombat policy
  learns from paired forks with the combat agent frozen.

## Method

- Recordings: `runs/act1-search-20261113/s24-n512` and `s24-n512-campaign`,
  1,024 public trajectories each, with their `search.json`. No private
  directory was opened.
- One process extracted every noncombat decision (context, candidates, the
  choice, HP, gold) and every fight's deck, relics and potions; this took four
  minutes. The policy probabilities come from running the frozen campaign
  bundle on the recorded decisions of 60 campaigns.
- The scripts are not in the repository. They are in the sessions' shared
  notes folder under `noncombat-proposal-scripts/`.
- Elapsed: about 30 minutes in all, for reading, extraction, analysis, the
  source search and this text. User wait: none.
