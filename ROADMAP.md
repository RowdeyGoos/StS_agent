# Roadmap

Priorities updated 2026-11-12. This file owns priorities;
[current status](docs/STATUS.md) owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

The requested non-training completion pass is complete for the declared pinned
single-player scope. The shared contract, fixed action encoding, Gym environments,
public data tools and bounded execution are delivered. The named bridge paths
have representative live evidence, the shared-v2 saved continuation reaches a
settled native ending, and no known correctness failure remains open in the
requested paths. The current package passed its release gate, installation and
exact cleanup checks; source and evidence are committed.

The final coverage work included the native Kifuda empty-confirm correction and
successful one-card toggle retest, automatic Neow pickups, Sozu-blocked Holster,
empty removal retaining Eternal, standalone first Sacrifice, shop spending/kind
variants, an assisted elite handoff and natural Orobas entry. Agent-managed Steam
launch, normal shutdown and restart worked across the controlled batches.
[Current status](docs/STATUS.md) owns exact results and limits; the
[live ledger](docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#prevention-removal-policy-variants-and-handoffs)
retains the separate boss-helper map stop with all actions reconciled.

Milestone 7 remains accepted by the user for the assisted potion campaign: all
its gameplay was policy-controlled through the native ending, with one reload
for the Waterfall Giant correction. Its original continuation result is unchanged;
another fresh campaign is not an acceptance requirement. The later shared-v2
ending is an assisted saved continuation with its own corrections and reloads,
not a fresh uninterrupted v2 certification. See the
[accepted scope](docs/AGENT_ENVIRONMENT.md#7-complete-live-campaign-traversal).

Further work should start from a new concrete requirement:

1. **Maintain the accepted package.** Reuse unchanged engine/consumer evidence,
   including the September 26 package refresh and its 406 agent checks, until
   affected inputs or the pinned game build change. Preserve exact source,
   artifact, test and cleanup bindings.
2. **Resolve new native discrepancies when observed.** Identify the caller and
   observable outcome first, then add the smallest implementation and validation
   needed. Unsupported shapes with no identified gameplay caller retain explicit
   limits; they are not an unbounded implementation queue.
3. **Improve Act 1 completion, combat first.** The training goal is Ironclad A0
   Act 1 clear rate across Overgrowth and Underdocks. The current focus is a
   well-functioning combat agent before the other aspects are added (user
   direction, 2026-11-12). The [combat overview](docs/COMBAT_OVERVIEW.md) owns
   the combat scoreboard, the record of every study and the open questions; this
   entry owns only what comes next.

   Where combat stands on the boss and elite benchmark:
   - Search during play is the only lever with a large, repeatable gain: 55.5%
     of bosses and 85.8% of elites at 24 simulations, against 48.7% and 79.1%
     for the best network alone. At 96 simulations it wins 60.2% of bosses, at
     four times the cost.
   - More PPO, architecture and feature changes, and distilling search into the
     network each moved bosses by a few points at most.
   - With perfect information at least 82.8% of the boss fights can be won: a
     player or a solver that sees the hidden state won them. The decks are not
     the main limit.
   - A planner with no network, which samples the unknown draw order and plans
     with the solver's beam search, wins 59.6% of bosses: 4.1 points above the
     network with 24-simulation search and level with 96-simulation search. It
     is an experiment on the headless engine, not a deployable agent.

   Sequence from the 2026-11-12 review. The user chose step 1, the ceiling
   measurement of step 2 and the planner test of step 4; the rest of the
   sequence and the pause list are proposed and await confirmation.
   1. **Freeze the map.** Done: the combat overview and this entry.
   2. **Measure the ceiling.** Done for the ceiling itself: see the
      [ceiling record](docs/evidence/COMBAT_CEILING_2026_11_12.md). The solver
      is a labelled privileged diagnostic: never the agent and never a training
      target. The 96-simulation search benchmark, outstanding since
      2026-11-01, is done for the bosses: see the
      [follow-up](docs/evidence/COMBAT_SEARCH_BENCHMARK_2026_10_17.md#follow-up-2026-11-13-96-simulations-on-the-boss-fights).
      Searched play in Act 1 with the fixed noncombat heuristic is measured
      as well: 24 simulations lift the clear rate from 18.2% to 27.5% on 512
      paired campaigns, +9.4 [+5.5, +13.3]; see the
      [Act 1 record](docs/evidence/ACT1_SEARCH_2026_11_13.md). The registered
      gate stays inconclusive, so search remains opt-in. With search the boss
      ends 64% of the lost campaigns, and bosses entered below 70% HP are won
      16% of the time against 49% above it. With the 500k campaign policy
      making the noncombat choices on the same starts, the clear rate rises
      from 42.8% to 50.6% and the bosses are won as often as on the benchmark.
      The noncombat choices are worth about three times what search is there.
   3. **Let the gap decide.** The solver wins far more than search does (+27
      points on bosses at 24 simulations, +21 at 96), so combat has room in
      principle and step 4 applies.
      Had it won little more, the next move would have been deck building
      around the frozen searched player.
   4. **Make search cheaper before making anything smarter.** A
      [profile](docs/evidence/SEARCH_PROFILE_2026_11_13.md) located the time:
      79% handles the public observation of each simulated step, the network
      itself took 9.5% and the game rules 9.9%. Three contained changes are
      done: search is 1.35 times faster with identical decisions. Reusing what
      is derived from shared card descriptions added 1.28 times on 2026-11-14,
      1.72 times together. A gain of
      several times needs a redesign of that path, which is not started; four
      times faster search is worth about 5 boss points at the measured rate.
      The leaf rollouts, over half of the search time, stay: at equal time
      search without them loses 3.8 boss points.
      Then measure strength against
      simulation count on the benchmark, relative to the ceiling. Train on
      search labels at scale only if that curve flattens early. Two points of
      that curve are measured on the bosses, 55.5% at 24 simulations and 60.2%
      at 96; it has not flattened, and cost per simulation is the limit. The
      first experiment is done: see the
      [planner record](docs/evidence/COMBAT_PUBLIC_PLANNER_2026_11_12.md).
      The first follow-up is done as well: counting only the enemies that
      must die as progress did not help on The Kin (45 wins against 49 of 100),
      so the cause of that weakness is open; see the
      [follow-up](docs/evidence/COMBAT_PUBLIC_PLANNER_2026_11_12.md#follow-up-2026-11-13-the-kin-and-the-progress-measure).
      Proposed follow-ups for the planner, in order:
      - measure strength against the number of worlds and lines;
      - try the network's value in place of its five hand-set numbers;
      - make it cheap, and build its worlds from the public belief path so that
        it no longer starts from the private engine state.

   Paused while search is the focus: further PPO variants, architecture and
   feature screens, reward shaping, single-boss specialists and larger
   distillation rounds. Keep the combat graph.

   Standing constraints:
   - Keep the noncombat heuristic fixed in hybrid Act 1 checks. Production
     defaults and parallel PPO remain in use. The user lifted this for one
     check on 2026-11-13, which used the 500k campaign policy instead. Whether
     that policy becomes the fixed noncombat controller awaits a decision.
   - Search stays opt-in until a paired Act 1 comparison clears its confidence
     gate. Native bridge receipts remain a separate gate.
   - Experimental results and generated presets do not change production
     defaults by themselves. Work after the original TEST exposure is
     exploratory and authorizes no further TEST run.
   - Full-campaign training is deferred until Act 1 progress is repeatable.
     Campaign-aware combat exit values, stronger full-run learning, throughput
     targets and a fresh uninterrupted shared-v2 campaign are later scopes.
     Representative bridge coverage does not establish strategic quality.

   Training milestones 1–7 are delivered. The [training guide](docs/AGENT_TRAINING.md)
   owns their usage and results, including the
   [Act 1 workflow](docs/AGENT_TRAINING.md#act-1-training-and-configurable-act-rewards)
   and the [search workflow](docs/AGENT_TRAINING.md#experimental-combat-search).
   The [search architecture](docs/COMBAT_SEARCH_ARCHITECTURE.md) owns the belief
   design and its remaining gates.

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns remaining evidence limits, and the
[headless backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md#hf-48--accept-complete-run-fidelity-and-close-coverage-gaps)
owns concrete engine discrepancies. Allocated off-screen transformation and
single-upgrade holders already have representative results; further tests should
address new behavior rather than repeat their geometry checks.

## Scope of further bridge implementation

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns implementation limits separately from the accepted representative coverage.
Rest selector cancellation, wider terminal reward screens and the named
full-producer pickup paths are implemented and have representative evidence.
Unsupported selector/pickup shapes without a concrete caller remain outside the
implementation queue. Multi-card Smith is not a native gameplay
requirement in the pinned assembly.

Use the [research map](docs/EVENT_INTERACTION_MAP.md) for source-backed callers;
its historical gap matrix is not a current task queue. Variable upgrades, enchantment
stacking/replacement and unallocated-holder mechanisms need a concrete caller/setup before implementation. Native cancellation
is confirmed for rest-site Smith/Cook, separately from optional-zero event selectors.
Plan shared capabilities from native dependencies, not event-name rules.

## Headless and learning direction

Prioritize faithful game logic in the [independent engine](docs/HEADLESS_ENGINE.md).
Implement and test cards, monsters, powers, items and run progression directly,
then integrate mature capabilities into actor/bridge consumers when useful.
Projection, encoding and training work must not gate ordinary gameplay features.
The old simulator/reduced backend and research pipelines are retired. Future
public observations and policy/data adapters must consume the current engine.

The [full-game backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md) owns feature
scope and acceptance cases. Strike+ is now ordinary game content; the experimental
per-upgrade profile is retired. Headless and bridge work can proceed in parallel
with disjoint source ownership and shared pinned-game rule evidence.

Public datasets and operational agent execution now consume the full-run
observations/encoding in HF-46/47. CPU imitation, bounded PPO and checkpoint
playback now use that interface. Stronger policies and search remain
subsequent work.
The [agent environment plan](docs/AGENT_ENVIRONMENT.md) defines the shared-contract,
bridge-adapter and Gymnasium milestones and their observable acceptance cases.
Its [shared contract and both bounded producers](docs/AGENT_CONTRACT.md) are
implemented, with the same public-only chooser over the combat/selection/reward/map
slice. Milestone 3's controlled native slice, separate map dispatch and cleanup
are accepted. Milestone 4's [fixed public encoding and Gymnasium environment](docs/AGENT_ENCODING.md)
are implemented. Milestone 5 adds full headless decision/content coverage and
`FullRunEnv`, with explicit exclusions from the existing live profile. Milestone 6
adds [public trajectories, the installed agent command and bounded workers](docs/AGENT_EXECUTION.md).
Milestone 7's assisted live traversal is accepted with its documented bridge-fix
reload. Further native coverage and stronger policies preserve the current
profile's explicit gaps and evidence requirements.

## Long-term destination

Use the faithful full-run engine to develop stronger policy/value
models and optional tactical/strategic search over shared legal candidates.
Expand content and certify performance under the pinned target, public-information
boundary and declared compute budget. See the
[target](docs/TARGET.md) for current evaluation requirements and the
[archived architecture plan](docs/archive/LONG_TERM_ARCHITECTURE_ROADMAP_2026_09_22.md)
for historical design detail.

Update this file when priorities change, not after every test run. For substantial
features, use available phase timings to check whether the streamlined process
reduces time to usable behavior without increasing regressions.
