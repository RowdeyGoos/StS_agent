# Combat agent overview

Updated 2026-11-13. This page is the map of the combat-agent work: where it
stands, what has been tried and what is still unknown. It owns the combat
scoreboard and the one-row-per-study record. The [roadmap](../ROADMAP.md) owns
what to do next, the [training guide](AGENT_TRAINING.md) owns commands and
implementation, and each linked evidence record owns its own details.

## Where combat stands

The scoreboard is the [boss and elite benchmark](evidence/BOSS_ELITE_BENCHMARK_2026_10_17.md):
589 boss and 1,139 elite fights, frozen at their first decision, from 1,024
Ironclad A0 Act 1 campaigns played by one collector. Rates weight each encounter
equally. A paired comparison resolves about 5 boss points and 2 elite points.
Normal fights are won about 98% of the time and are not on the scoreboard.

| Player | Bosses | Elites | Thinking time |
| --- | ---: | ---: | --- |
| Network with search, 96 simulations | **60.2%** | not run | 6.1 s per searched decision |
| Planner without a network, 8 sampled worlds with 4 lines each (experimental) | 59.6% | not run | 5.3 s per decision |
| Network with search, 24 simulations | 55.5% | **85.8%** | 1.9 s per searched decision |
| Planner without a network, 1 sampled world with 1 line (experimental) | 49.8% | not run | 0.4 s per decision |
| Best network alone (Vantom specialist, 250k) | 48.7% | 79.1% | none |
| Combat PPO 250k with imitation, seeds 1 / 2 | 43.4% / 45.6% | 79.3% / 79.6% | none |
| Combat PPO 250k, seeds 1 / 2 | 38.5% / 43.0% | 75.7% / 78.2% | none |
| Act 1 campaign PPO 500k | 36.7% | 75.8% | none |
| Heuristic | 15.1% | 66.7% | none |
| *Fight won by at least one of 75 players* | *69.5%* | *90.9%* | not a player |
| *Perfect-information solver, alone* | *81.6%* | *not run on all elites* | not a player |
| *Fight won by a player or the solver* | *82.8%* | *94.5%* | not a player |

A simulation is one hypothetical continuation that search plays out before it
chooses. The two leading rows are level: their paired difference is +0.6
[−2.8, +4.1] points. The search times were measured before the speed changes
of 2026-11-13 and 2026-11-14, which together made search 1.72 times faster
with identical decisions.

The benchmark's boss rates carry over to campaign play. In 512 Act 1 campaigns
where the collector's campaign policy made the noncombat choices, the best
network won 50.7% of the bosses it reached and 56.6% with 24-simulation
search, and cleared Act 1 in 42.8% and 50.6% of the campaigns; see the
[Act 1 record](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-the-campaign-policy-makes-the-noncombat-choices).

The planner has no network and no training. For each decision it samples
hypothetical worlds in which the unknown draw order is reshuffled, plans in each
with the solver's beam search, and votes. It is an experiment on the headless
engine, not the production search path and not a deployable agent. See the
[planner record](evidence/COMBAT_PUBLIC_PLANNER_2026_11_12.md).

The last three rows are bounds, not players.
- **Any player** counts a fight as won if any evaluated player won it. One
  policy has not achieved this: six near-identical learners each win about 48.6%
  of bosses, but at least one of them wins 60.6%. See the
  [any-player record](evidence/COMBAT_ANY_PLAYER_WINS_2026_11_12.md).
- **The solver** may see the true draw order and RNG and keeps up to 64 lines of
  play at once. Every win it reports was replayed to a victory in the
  benchmark's own environment. No player can do better than this ceiling, and
  none can be expected to reach it. With a single line the solver wins 51.0% of
  bosses. See the [ceiling record](evidence/COMBAT_CEILING_2026_11_12.md).

| Encounter | Fights | Best network | Search | Any player | Solver or any player | Won by neither |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast (boss) | 100 | 78.0% | 82.0% | 89.0% | 97.0% | 3 |
| The Kin (boss) | 100 | 48.0% | 60.0% | 73.0% | 82.0% | 18 |
| Vantom (boss) | 120 | 55.0% | 63.3% | 74.2% | 82.5% | 21 |
| Lagavulin Matriarch (boss) | 85 | 28.2% | 35.3% | 52.9% | 75.3% | 21 |
| Soul Fysh (boss) | 97 | 59.8% | 66.0% | 89.7% | 96.9% | 3 |
| Waterfall Giant (boss) | 87 | 23.0% | 26.4% | 37.9% | 63.2% | 32 |
| Bygone Effigy (elite) | 204 | 81.9% | 86.8% | 92.6% | 98.0% | 4 |
| Byrdonis (elite) | 201 | 83.6% | 85.6% | 89.1% | 92.0% | 16 |
| Phrog Parasite (elite) | 207 | 81.6% | 89.9% | 95.7% | 97.6% | 5 |
| Phantasmal Gardeners (elite) | 181 | 68.0% | 83.4% | 88.4% | 93.4% | 12 |
| Skulking Colony (elite) | 170 | 81.8% | 84.7% | 88.2% | 92.4% | 13 |
| Terror Eel (elite) | 176 | 77.8% | 84.7% | 91.5% | 93.8% | 11 |

## What works and what does not

| Lever | Best measured effect | Reading |
| --- | --- | --- |
| [Search during play](#search-during-play) | +6.8 boss and +6.7 elite points at 24 simulations, positive on all 12 encounters; 96 simulations add 4.7 boss points at four times the cost. In Act 1, 24 simulations add 8 to 9 clear points | The only large, repeatable gain. It was still growing at 96 simulations; cost is the limit |
| [Planning without a network](#search-during-play) | 59.6% of bosses: +10.9 over the best network, +4.1 over 24-simulation search and level with 96-simulation search | No learning, five hand-set numbers. Wins different fights than search does. Slow, weak on The Kin and not deployable as built |
| [Imitating successful hard fights](#imitation) | +2.7 to +4.9 boss points | Small but real |
| [The combat-graph network](#network-architecture-and-features) | +5.9 points over the original graph (2026-10-01) | Adopted. Nothing tried since has beaten it |
| [More PPO training](#ppo-training) | about 0 on bosses, +2 on elites after 246k more decisions | Plateaued. Long runs on few fights overfit |
| [Learning from search](#learning-from-search) | recovers 10–20% of search's gain; under one point per doubling of labels | Slow at the scale tried |
| [Rewards and extra inputs](#rewards-and-inputs-on-the-vantom-panel) | no endpoint beat its parent | Unresolved: tested only on a 42-fight panel |

## What is not known

1. **How much of the perfect-information ceiling a real player can reach.** With
   hindsight at least 82.8% of the boss fights can be won. The best public
   players so far win about 60%: the network with 96-simulation search (60.2%)
   and the planner without a network (59.6%). The decks are therefore not the
   main limit. How much of the remaining 22 points a larger budget or a learned
   evaluation can recover is unmeasured.
2. **How much a larger search budget buys beyond 96 simulations.** On the
   bosses the network's search wins 55.5% at 24 simulations and 60.2% at 96:
   four times the cost bought 4.7 points, and the gain had not flattened.
   Elites at 96 simulations and any larger budget are unmeasured on the
   benchmark; the 256-simulation result comes from 64 authored fights at 30 s
   per decision. For the planner only two settings are measured: one world with
   one line (49.8%) and eight worlds with four lines (59.6%).
3. **What searched play is worth in Act 1 beyond 24 simulations.** At 24
   simulations search lifts the Act 1 clear rate from 42.8% to 50.6% when the
   500k campaign policy makes the noncombat choices, +7.8 [+3.9, +11.7], and
   from 18.2% to 27.5% with the noncombat heuristic, +9.4 [+5.5, +13.3]; both
   on the same 512 starts, see the [Act 1 record](evidence/ACT1_SEARCH_2026_11_13.md).
   The registered gate for making search the default uses a wider interval
   and stays inconclusive in both. 96 simulations are unmeasured in Act 1, and
   so is the campaign policy playing its own fights on these starts. With
   search the boss ends four in five of the lost campaigns.
4. **How much of a boss loss is decided before the fight.** Neither a player nor
   the solver has won 98 of the 589 boss fights. That is the most that decks and
   HP alone can still explain, and it is not a count of unwinnable fights. HP on
   arrival matters even with hindsight: 92.9% of the bosses entered with at
   least 85% HP can be won, and 60.3% of the 141 entered below 70%. All decks
   come from one collector, the Act 1 500k policy. In Act 1 the noncombat
   choices are worth about three times what search is: on the same starts that
   policy's choices add 23 to 25 clear points over the heuristic's, and search
   adds 8 to 9; see the [comparison](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-the-campaign-policy-makes-the-noncombat-choices). The heuristic's campaigns
   reach the boss with more upgrades and relics but 74% HP against 88%, and
   lose three times as many campaigns at elites. Which choices matter most is
   not separated. With the heuristic, bosses entered with at least 70% HP are
   won 49% of the time under search and those entered below it 16%; see the
   [fight breakdown](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-which-fights-end-the-campaigns). Search values a win at 1 plus a tenth of the
   HP fraction kept. In a first fight that both arms always won it kept 0.8 HP
   more than the network. How much HP a player that valued it more could keep,
   and what that is worth at the boss, is unmeasured.
5. **Whether search can be made much cheaper.** A
   [profile](evidence/SEARCH_PROFILE_2026_11_13.md) shows that 79% of the network search's time handles the
   public observation of each simulated step: building it, copying and
   checking it, computing keys from it and encoding it. The network itself
   took 9.5% and the game rules 9.9%. Three contained changes then made
   search 1.35 times faster with identical decisions, and reusing what is
   derived from shared card descriptions another 1.28 times: 1.72 times
   together, at 0.88 s per searched decision. Handling the observation is
   still 65% of the search time. A gain of several times needs the rest of
   the observation, the map and the cards, to be reused between steps, which
   is a redesign. The greedy leaf
   rollouts take over half of the time and pay for themselves: at equal time,
   search without them loses 3.8 boss points. At the measured 2.3
   boss points per doubling of simulations, four times faster search is worth
   about 5 points. The speed work so
   far kept the public projection inside every simulation. The planner skips the
   projection but restores a full engine snapshot for every simulated command.
6. **Whether learning from search compounds over rounds.** Not shown. Three
   rounds were run on a 42-fight panel and one round on the benchmark; the
   largest label set is 60,738 decisions.
7. **Whether the planner and the network help each other.** They win different
   boss fights: 96-simulation search won 56 that the planner lost, the planner
   52 that search lost, and one or the other won 69.0%. That alone does not
   show that a combination would gain: six near-identical learners differ as
   much among themselves (48.6% each, 60.6% for at least one of them). The
   clear difference is The Kin, where search is 16 points ahead. The planner ranks
   states by five hand-set numbers. The network's value has not been tried in
   its place, and the planner has not been run on elites or in Act 1.
8. **Why the planner is weak on The Kin.** It wins 49% there, against 60% and
   65% for the network with 24 and 96 simulations. Leaving the Kin's followers
   out of its progress measure did not help.

## Study record

One row per study, newest last within each lever. Verdicts:
- **Helps**: a measured gain whose interval excludes zero.
- **Small**: a gain of about a point, at the edge of what the benchmark resolves.
- **No gain**: the panel could have shown a gain of a few points and did not.
- **Unresolved**: the panel was too small to tell, or the interval includes zero.
- **Tooling**: makes the work faster or possible; not a strength result.

Bracketed ranges are 95% paired intervals in percentage points.

### Search during play

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-10-04 | First public-information search, starter decks, 128 starts | 85/128 wins for greedy, root-only and Gumbel search alike | No gain on easy fights | [pilot](evidence/COMBAT_SEARCH_2026_10_04.md), [benefit](evidence/COMBAT_SEARCH_BENEFIT_2026_10_04.md) |
| 2026-10-05 | Developed decks, 32 harder authored starts | greedy 22, Gumbel 23 | Unresolved | [developed benchmark](evidence/COMBAT_SEARCH_DEVELOPED_BENCHMARK_2026_10_05.md) |
| 2026-10-06 | Leaf rollouts: 24 simulations with 4 greedy leaf plays, 128 fresh authored fights | 90 to 100 wins, +7.8 [+3.1, +13.3] | Helps | [rollout search](evidence/COMBAT_SEARCH_LEARNING_2026_10_06.md) |
| 2026-10-06 | 256 simulations with 16 leaf plays, 64 fresh authored fights | 56 wins against 51 at 24 simulations, +7.8 [0.0, +15.6]; 29.8 s per decision | Unresolved; too slow | [strength](evidence/COMBAT_SEARCH_STRENGTH_2026_10_06.md) |
| 2026-10-07 | Value weight, final choice and longer leaf continuations | none beat the 24-simulation reference (47/64 against 49/64 on confirmation) | No gain | [selection](evidence/COMBAT_SEARCH_SELECTION_2026_10_07.md) |
| 2026-10-07 | Search on the Vantom specialist, 42 fights | 26/42 with and without search; 28/42 after a coverage repair | Unresolved | [specialist](evidence/VANTOM_SPECIALIST_SEARCH_2026_10_07.md), [repair](evidence/VANTOM_SEARCH_TRAINING_2026_10_08.md) |
| 2026-10-09 | Search in Act 1, four paired campaigns | one clear against none | Unresolved | [campaign search](evidence/CAMPAIGN_SEARCH_VALIDATION_2026_10_09.md) |
| 2026-10-17 | **Search on the benchmark, 24 simulations** | bosses +6.8 [+4.1, +9.7], elites +6.7 [+5.3, +8.2] | **Helps** | [search benchmark](evidence/COMBAT_SEARCH_BENCHMARK_2026_10_17.md) |
| 2026-11-01 | 96 against 24 simulations, 768 paired training fights | +3.5 [+1.6, +5.5], bosses +5.0; 7.4 s against 1.9 s per decision | Helps; on training fights | [search targets](evidence/COMBAT_SEARCH_TARGETS_2026_11_01.md) |
| 2026-11-12 | Planner without a network on all 589 bosses: sampled draw orders, the solver's beam search, a vote | 8 worlds with 4 lines: 59.6%, +4.1 [+0.5, +7.7] over the network with search and +10.9 [+7.4, +14.7] over the best network; 1 world with 1 line: 49.8% | **Helps** | [public planner](evidence/COMBAT_PUBLIC_PLANNER_2026_11_12.md) |
| 2026-11-13 | Planner on the 100 Kin fights, with progress counting only the enemies that must die | 45 wins against 49 unchanged, −4.0 [−12.0, +4.0] | No gain | [planner follow-up](evidence/COMBAT_PUBLIC_PLANNER_2026_11_12.md#follow-up-2026-11-13-the-kin-and-the-progress-measure) |
| 2026-11-13 | **Search on the benchmark's 589 bosses, 96 simulations** | 60.2%: +4.7 [+2.3, +7.3] over 24 simulations and +11.5 [+8.6, +14.5] over the network; level with the planner, +0.6 [−2.8, +4.1]; 6.1 s against 1.5 s per searched decision | **Helps** | [search benchmark follow-up](evidence/COMBAT_SEARCH_BENCHMARK_2026_10_17.md#follow-up-2026-11-13-96-simulations-on-the-boss-fights) |
| 2026-11-13 | Leaf rollouts at equal search time on the 589 bosses: 54 simulations without rollouts and 32 with two steps, against 24 with four | without rollouts 51.7%, −3.8 [−6.5, −1.1]; two steps 54.8%, −0.8 [−3.3, +1.6] | No gain; the four-step rollouts pay for themselves | [rollout test](evidence/COMBAT_SEARCH_BENCHMARK_2026_10_17.md#follow-up-2026-11-13-leaf-rollouts-at-equal-search-time) |
| 2026-11-13 | **Search in Act 1, 24 simulations, 512 paired campaigns** with the fixed noncombat heuristic | Act 1 clears 18.2% to 27.5%, +9.4 [+5.5, +13.3]; boss reached 64.1% to 74.0%; the registered Hoeffding gate stays inconclusive (−2.6 to +21.4) | **Helps**; search stays opt-in | [Act 1 search](evidence/ACT1_SEARCH_2026_11_13.md) |
| 2026-11-13 | **The same comparison with the 500k campaign policy making the noncombat choices**, same 512 starts | Act 1 clears 42.8% to 50.6%, +7.8 [+3.9, +11.7]; bosses reached are won 50.7% and 56.6%, as on the benchmark; the Hoeffding gate stays inconclusive (−4.2 to +19.8) | **Helps**; search stays opt-in | [campaign policy's choices](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-the-campaign-policy-makes-the-noncombat-choices) |

### Learning from search

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-10-06 | One learning round from 480 authored training fights | student with search 100/128, the same as its teacher with search | No gain | [rollout search](evidence/COMBAT_SEARCH_LEARNING_2026_10_06.md), [strength](evidence/COMBAT_SEARCH_STRENGTH_2026_10_06.md) |
| 2026-10-08 | Vantom search training, three rounds of 50k decisions | student with search 25, 27, then 28 of 42; the PPO specialist with search also 28 | Unresolved | [round 1](evidence/VANTOM_SEARCH_TRAINING_2026_10_08.md), [round 2](evidence/VANTOM_SEARCH_ROUND2_2026_10_08.md), [round 3](evidence/VANTOM_SEARCH_ROUND3_2026_10_08.md) |
| 2026-10-08 | Replay and selective reanalysis of saved targets | 26 and 24 of 42 with search, against 28 before | Unresolved | [reuse](evidence/VANTOM_SEARCH_REUSE_2026_10_08.md) |
| 2026-10-18 | Distilling 60,738 search labels into the specialist; 1–16 epochs, three learning rates | bosses +0.4 to +1.3, elites +0.7 to +1.1: 10–20% of search's gain | Small | [distillation](evidence/COMBAT_SEARCH_DISTILLATION_2026_10_18.md) |
| 2026-10-22 | Six representations fitted to those labels | none fit held-out campaigns better than the combat graph; width 128 equals width 48 | No gain | [representation screen](evidence/COMBAT_REPRESENTATION_SCREEN_2026_10_22.md) |
| 2026-11-01 | More labels, and labels from 96 simulations | 0.006 nats per doubling; 0.014–0.019 nats from stronger labels; about 0.05 nats is worth one win point | Small | [search targets](evidence/COMBAT_SEARCH_TARGETS_2026_11_01.md) |

### PPO training

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-09-30 | Fresh combat PPO to 250k and 500k decisions | validation wins 218, 214 and 213 of 250 at 50k, 250k and 500k | No gain past 50k | [250k](AGENT_TRAINING.md#fresh-combat-policy-250k-decisions-2026-09-30), [plateau diagnostic](AGENT_TRAINING.md#combat-learning-plateau-diagnostic-2026-10-01) |
| 2026-10-02 | Seven-hour pass: schedules, more data, wider and deeper models, checkpoint averaging | +100k PPO left the locked 514-fight test at 69.8% against 69.7% | No gain | [seven-hour research](AGENT_TRAINING.md#seven-hour-combat-research-2026-10-02) |
| 2026-10-02 | Vantom-only PPO, 250k decisions | Vantom panel 22 to 26 of 42; on the benchmark +3.0 boss [+0.3, +5.8] over its initializer | Helps | [specialist](AGENT_TRAINING.md#first-vantom-specialist-training-experiment), [benchmark](evidence/BOSS_ELITE_BENCHMARK_2026_10_17.md) |
| 2026-10-02 | Optimizer and critic resets on continuation | did not explain the regression | No gain | [continuation diagnostic](AGENT_TRAINING.md#vantom-continuation-diagnostic) |
| 2026-10-03 | The same specialist continued to 500k and 1M | training fights 63 to 76 of 101; validation 26 to 21 of 42 | No gain; overfits | [continuation](AGENT_TRAINING.md#vantom-specialist-continuation-to-500k-2026-10-03) |
| 2026-10-15 | One PPO recipe across models, 36 learners | minibatch 64 was the strongest alternative but failed the registered gates | Unresolved | [shared PPO](evidence/VANTOM_SHARED_PPO_2026_10_15.md) |
| 2026-10-17 | 246k more decisions from the specialist on all bosses and elites; hidden-state resampling | bosses +0.2 [−1.9, +2.4], elites +2.0 [+0.7, +3.2]; resampling −0.7 [−2.1, +0.8] | No gain on bosses | [hidden state](evidence/COMBAT_HIDDEN_STATE_2026_10_17.md) |
| 2026-10-18 | Minibatch 64 for corpus PPO | 12.5% faster; bosses +1.7 [+0.2, +3.3], elites −0.3 [−1.2, +0.6] | Tooling; adopted in the preset | [minibatch](evidence/COMBAT_MINIBATCH_2026_10_18.md) |

### Imitation

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-10-02 | Imitating 87 successful elite and boss fights, 8k updates, two seeds | benchmark bosses +4.9 [+2.1, +8.1] and +2.7 [−0.3, +5.8]; locked test bosses 32.9% to 41.4% | Helps | [seven-hour research](AGENT_TRAINING.md#seven-hour-combat-research-2026-10-02), [benchmark](evidence/BOSS_ELITE_BENCHMARK_2026_10_17.md) |

### Network architecture and features

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-10-01 | Combat channels and typed pools against the original graph, 250k decisions, two seeds | +5.9 [+3.4, +9.2] balanced sampled wins | Helps; adopted as the combat graph | [representation](AGENT_TRAINING.md#combat-representation-experiment) |
| 2026-10-03 | Pooled MLP and entity attention against the graph | 51.2% and 53.6% against 50.0% of 42 fights | Unresolved | [non-graph](AGENT_TRAINING.md#non-graph-combat-architectures) |
| 2026-10-12 | Features, identities and architectures, 96 learners | basic flat with identities led the screen; finalist and feature-removal differences unresolved | Unresolved | [feature study](evidence/VANTOM_FEATURE_STUDY_2026_10_12.md) |
| 2026-10-13 | Richer inputs for flat MLPs at equal width, 18 learners | richer inputs did not help | No gain | [flat width](evidence/VANTOM_FLAT_WIDTH_2026_10_13.md) |
| 2026-10-14 | Compact and hierarchical entity encoders, 24 learners | 6.7× less input storage; no strength advantage established | No gain | [entity encoding](evidence/VANTOM_ENTITY_ENCODING_2026_10_14.md) |
| 2026-10-22 | Six representations fitted to search labels | see [learning from search](#learning-from-search) | No gain | [representation screen](evidence/COMBAT_REPRESENTATION_SCREEN_2026_10_22.md) |

### Rewards and inputs on the Vantom panel

Each arm fine-tuned the 250k specialist for 50k decisions with two seeds, except
the from-initialization study. Results are mean greedy wins on 42 fights; the
unchanged specialist wins 61.9%.

| Date | Study | Result | Verdict | Record |
| --- | --- | --- | --- | --- |
| 2026-10-02 | Potential-based reward shaping | control 47.6%, enemy HP 48.8%, enemy and player HP 53.6% | Unresolved | [shaping](AGENT_TRAINING.md#vantom-potential-shaping-experiment) |
| 2026-10-02 | Action previews of damage and Slippery removed | control 52.4%, previews 52.4% and 48.8% | Unresolved | [previews](AGENT_TRAINING.md#vantom-action-preview-experiment) |
| 2026-10-03 | Partial credit for enemy HP on defeat | control 56.0%, credit 48.8% and 51.2% | Unresolved | [defeat reward](AGENT_TRAINING.md#vantom-enemy-health-defeat-reward-experiment-2026-10-03) |
| 2026-10-04 | Complete catalog vocabulary and item descriptions | control 50.0%, vocabulary 51.2%, descriptions 48.8% | Unresolved | [catalog pilot](AGENT_TRAINING.md#vantom-catalog-representation-pilot-2026-10-04) |
| 2026-10-04 | The same representations trained from initialization | control 54.8%, vocabulary 59.5%, descriptions 53.6% | Unresolved | [from initialization](AGENT_TRAINING.md#vantom-representations-from-initialization-2026-10-04) |

### Speed and tooling

| Date | Study | Result | Record |
| --- | --- | --- | --- |
| 2026-10-04 | Public-belief machinery for search: Act 1 coverage, direct sampling, input views | all 42 ordinary Act 1 encounters supported | [coverage](evidence/COMBAT_BELIEF_COVERAGE_2026_10_04.md), [direct sampling](evidence/COMBAT_DIRECT_SAMPLING_2026_10_04.md), [input views](evidence/COMBAT_SEARCH_LEARNING_2026_10_04.md) |
| 2026-10-07 | Search worker scaling and inference | 16 workers give 2.1× the throughput of 4; compact inference cut search time 35% | [workers](evidence/SEARCH_WORKER_SCALING_2026_10_07.md), [inference](evidence/SEARCH_INFERENCE_2026_10_08.md) |
| 2026-10-08 | Search training speed | 12.8% less search time | [training speed](evidence/SEARCH_TRAINING_SPEED_2026_10_08.md) |
| 2026-10-11 | One search workflow for fixtures, Vantom starts and campaigns | 935 Vantom starts verified | [consolidation](evidence/SEARCH_WORKFLOW_CONSOLIDATION_2026_10_11.md) |
| 2026-10-17 | Engine speed, behaviour-identical | 1.5–2.8× faster play, snapshots and forks; the engine is about 13% of greedy play time | [engine speed](evidence/ENGINE_SPEED_2026_10_17.md) |
| 2026-10-18 | PPO training speed, bit-identical | 1.36× faster | [training speed](evidence/TRAINING_SPEED_2026_10_18.md) |
| 2026-11-12 | Fights won by any player, from existing reports | 69.5% of bosses and 90.9% of elites | [any player](evidence/COMBAT_ANY_PLAYER_WINS_2026_11_12.md) |
| 2026-11-12 | Perfect-information solver on all 589 bosses and the 102 elites no player had won | a player or the solver won 82.8% of bosses and 94.5% of elites; the solver alone 81.6% of bosses, 51.0% with a single line | [ceiling](evidence/COMBAT_CEILING_2026_11_12.md) |
| 2026-11-13 | Where the network search's time goes: direct timers on six boss fights | 79% handles the public observation of each simulated step; the network is 9.5% and the game rules 9.9% | [search profile](evidence/SEARCH_PROFILE_2026_11_13.md) |
| 2026-11-13 | Search speed, decision-identical: no copy of simulated observations, one path walk, reused card signatures | 1.35× faster on the 589 bosses with 16 workers, 1.50× on one worker; all 19,260 searched decisions unchanged | [follow-up](evidence/SEARCH_PROFILE_2026_11_13.md#follow-up-same-day-the-three-contained-changes) |
| 2026-11-14 | Search speed, decision-identical: readers reuse what they derive from shared card descriptions | 1.28× faster on the 589 bosses with 16 workers, 1.22× on one worker; 1.72× with the changes of 2026-11-13; all 19,260 searched decisions unchanged | [second follow-up](evidence/SEARCH_PROFILE_2026_11_13.md#follow-up-2026-11-14-shared-card-descriptions) |

### Act 1 results for context

| Date | Study | Result | Record |
| --- | --- | --- | --- |
| 2026-09-30 | Act 1 campaign PPO, 256 held-out starts | 56 clears (21.9%) at 250k, 23 for its initializer, 14 for the heuristic; formally inconclusive | [held-out test](AGENT_TRAINING.md#held-out-act-1-test-2026-09-30) |
| 2026-10-02 | Combat models in Act 1, 32 new campaigns | 48.4% and 50.0% clears, against 37.5% for the campaign model alone; difference not established | [seven-hour research](AGENT_TRAINING.md#seven-hour-combat-research-2026-10-02) |
| 2026-11-13 | Which fights end the 512 paired Act 1 campaigns of the search comparison | with search 238 of 371 lost campaigns end at the boss, 81 at an elite and 52 in a normal fight; bosses are entered at 74% HP against 84% on the benchmark | [fight breakdown](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-which-fights-end-the-campaigns) |
| 2026-11-13 | Who makes the noncombat choices, on the same 512 starts: the 500k campaign policy against the heuristic | +24.6 [+19.5, +29.5] clear points for the network and +23.0 [+17.6, +28.5] with search; boss entered at 88% HP against 74%, 25 campaigns lost at elites against 81 | [comparison](evidence/ACT1_SEARCH_2026_11_13.md#follow-up-same-day-the-campaign-policy-makes-the-noncombat-choices) |

## Fight panels

Results from different panels cannot be compared with each other.

| Panel | Size | Used by | Caveat |
| --- | --- | --- | --- |
| Boss and elite benchmark | 589 boss and 1,139 elite openings | the hidden-state, search, minibatch and distillation studies | A reused development panel, so it supports no held-out claim |
| Vantom panel | 42 openings of one boss | Vantom PPO, rewards, inputs, architectures, search training | Resolves only about 20 points; its reserved test was used by the feature study |
| Authored developed-deck fights | 48–128 starts from 12 deck and encounter families | search studies of 2026-10-05 to 2026-10-07 | Hand-built decks, not campaign decks |
| Combat corpus validation and locked test | 250 and 537 validation openings; 514 locked test fights with 35 bosses | combat PPO and the seven-hour pass | Mostly normal fights; the locked test is used up |
| Act 1 campaigns | 64 development, 256 held-out and 32 fresh starts; 512 validation starts for the search comparison | Act 1 clear rate | The held-out starts are used up. Clear rates depend on who makes the noncombat choices: 18% to 28% with the heuristic and 43% to 51% with the 500k campaign policy on the same 512 starts |

## Keeping this page current

- A new study adds one row to the study record. Its details stay in its evidence
  record.
- Only results on the boss and elite benchmark change the scoreboard.
- Change the lever table and the open questions only when a result changes the
  reading, not for every study.
- Priorities and next steps belong in the [roadmap](../ROADMAP.md).
