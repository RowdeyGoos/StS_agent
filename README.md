# StS Agent

Research toward a functional, eventually near-optimal Slay the Spire 2 agent.
The repository contains these complementary systems:

- An independent headless game engine for implementing cards, combat and persistent run rules.
- Combat research adapters for RL experiments, traces and exact small-combat search.
- A reduced headless run environment with public decision contracts, datasets and
  a deterministic behavior-cloning smoke. Progression rules are structural fixtures.
- A live-game bridge with bounded combat, reward, map, shop, rest and generic
  event capabilities. Supported event interactions are discovered by shared
  mechanisms, without adding an event-name registration for each caller.

This is not yet a complete autonomous agent or a verified full-game simulator.
[Current status](docs/STATUS.md) distinguishes implemented,
fixture-tested and live-demonstrated behavior, including the successful direct
off-screen transformation-card test.

Requires Python 3.10+. New coding sessions follow [AGENTS.md](AGENTS.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

For only the pure-Python simulator, `pip install -e .` is sufficient.
`requirements.txt` adds Gymnasium, PyTorch and Optuna.

## Implementing the game

Start with [`game/headless/`](game/headless/) and the [engine guide](docs/HEADLESS_ENGINE.md).
Game rules run directly through `CombatEngine` and `RunEngine`, without public
projections, encoders or training. Cards own their effect/upgrade definitions;
content catalogs and mutable instances are separate. All 85 single-player Ironclad
card definitions and their upgrades are implemented, including their shared powers,
autoplay, replay, card generation and pile choices. Demonic Shield and Tank are
excluded as multiplayer-only; basic/Ancient cards do not enter ordinary rewards.
All **53 single-player colorless cards** and both upgrade levels also execute,
including optional selections, retained hands, delayed powers and combat-generated
gold/potions. Eleven multiplayer-only colorless cards are excluded. Colorless
merchant slots and transformations use the full solo pool. See the
[colorless implementation and limits](docs/HEADLESS_ENGINE.md#colorless-cards).

The [solo Act 1 relic rules](docs/HEADLESS_ENGINE.md#relics) cover the audited
232-definition inventory, including all 99 solo Ancient relics, nested pickup choices, combat triggers,
shop/rest/reward modifiers and persistent counters. Generated runs use the full
ordinary/merchant relic pools. All 232 are supported by the default catalog,
including Kaleidoscope and 320 ordinary foreign cards; curse generation retains its
content subset. All **48 ordinary Ironclad-accessible potions**, both event potions
and Potion-Shaped Rock are implemented. Generated runs use the complete ordinary
potion pool, including rarity-based rewards/shops, automatic Fairy revival and
resumable card choices. See [potion rules and scope](docs/HEADLESS_ENGINE.md#potions).

Generated Act 1 runs now default to the pinned native RNG algorithm and reward
probability rules, including persistent relic grab bags and 13-slot merchants.
Native startup queues and complete Act 1 maps match direct assembly reference
seeds for the declared solo/all-unlocked Overgrowth start. Authored slices retain
their fixture generator. Runtime acquisition now applies native
relic predicates, shop filters and marked card-reward pool rules. Encounter composition,
HP, opening AI and initial/refill shuffle order also match native method fixtures.
Combat card-generation factories now match native pool, selection and RNG reference
cases, including potion offers. Bottled Potential, Innate/Stratagem/Abacus ordering
and generated Stomp entry now follow pinned source rules. Whole-run same-seed parity
still requires broader interaction checks. Random/area/targeted multihit damage,
deaths and Phrog spawns now match native attack-command reference cases; see [native generation and limits](docs/HEADLESS_ENGINE.md#native-randomness-and-generation).

The older experiment APIs
consume the same combat engine. Full target-game content and progression remain
unfinished; see the [feature backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md).

```bash
PYTHONPATH=. python -m pytest -q tests/headless
sts-headless-play --seed 2 --rest-choice smith --verify-restore
sts-headless-play --route overgrowth --path right --seed 2 --rest-choice rest --verify-restore
```

The playable first slice starts Ironclad at Ascension 0, fights Nibbit, collects
rewards, rests or upgrades a card, then fights Overgrowth slimes and collects the
second rewards. It includes Burning Blood and Fire/Block Potions. The map and item
pools are restricted; Ironclad rewards use the full single-player pool.
`slice_complete` is not full-game victory.
Use `--rest-choice rest` for the healing path and `--trace` to print every command.
The optional `--route overgrowth` plays four combats with two branches: choose
whether slimes or Fuzzy Wurm comes second, fight the other third, rest/smith, then
choose Mawler, paired Nibbits or the Byrdonis elite. Elite rewards include 35–45
gold and a relic from Strawberry/Pear/Mango, which permanently raises maximum HP
and heals on pickup. `--path right` selects the elite; `left` selects Mawler.
Add `--route overgrowth-act1` for an event fork and a treasure chest after
the third fight, followed
by the fourth fight, an optional shop, a second rest site and Vantom. Opening the
chest grants 42–52 gold; its relic can be taken or skipped. The restricted fruit
pool depletes on offers and falls back to Circlet when exhausted. `--path left` visits the shop; `right` bypasses it. The shop sells
supported cards, a fruit relic and Fire/Block Potions, and removes a chosen deck
card for 75 gold (25 more per prior shop removal). The demo buys one affordable
card and removes a starter if it can afford both; direct commands allow any legal
purchase sequence. Shop choices also support `--verify-restore`.
Jungle Maze Adventure offers Solo Quest (18 damage for more gold) or Join Forces
(less gold, no damage). The demo chooses Join Forces. Both payouts are fixed on
event entry, and event choices support `--verify-restore`. The left path visits
Jungle Maze; the right visits Aroma of Chaos. Aroma offers Let Go (transform one
card) or Maintain Control (upgrade one). Its mandatory card choice resolves
automatically for zero or one eligible card. The demo upgrades Bash when possible.
Transformations use all 80 common/uncommon/rare Ironclad cards, exclude the
original definition and create a new unupgraded card in the same deck position.
This route also offers Sword Boomerang, including its four-hit upgrade.
Leaving the boss rewards records `act_complete` for Act 1; it does not declare
full-game victory. The simple demo player can lose on this route. Boss rewards
use the full single-player Ironclad rare-card pool.

All **22 native Overgrowth encounters** are implemented at A0: 16 hallway/easy
encounters, three elites and three bosses, covering 29 monster types including
minions and all Ruby Raider variants. The authored Act 1 route accepts optional
`--hallway`, `--elite` and `--boss` encounter IDs (listed by `--help`):

```bash
sts-headless-play --route overgrowth-act1 --path right --rest-choice rest --seed 2 --elite overgrowth_phrog_parasite --boss overgrowth_ceremonial_beast --verify-restore
sts-headless-play --route overgrowth-act1 --path left --rest-choice rest --seed 2 --hallway overgrowth_fogmog --boss overgrowth_the_kin --verify-restore
```

Hallway overrides replace the left fourth-fight branch; elite overrides replace
the right fourth-fight branch. Boss selection replaces the final fight. These
options exercise content on the existing five-fight route; native map generation,
encounter selection and full card/item/event pools remain unfinished.
[Complete roster and validation](docs/evidence/overgrowth_roster_2026_09_13.md).

A generated full-length route is also available:

```bash
sts-headless-play --route overgrowth-generated --seed 2 --path left --rest-choice rest --verify-restore
```

It adds 15 map rows plus a boss, branching paths and run-owned encounter queues
(first three hallway fights weak, then normal encounters; separate elites).
The default profile prunes duplicate paths and resolves unknown markers once on
entry using native base odds. It assumes all encounters seen and uses restricted
event/card/item pools. Events now use a saved shuffled queue and repeat only after
the supported unique events are exhausted. The generated event pool now also
includes Tablet of Truth (healing or repeated maximum-HP costs for upgrades) and
Morphic Grove (maximum HP or spending all gold to transform two cards), with
Morphic Grove's native entry conditions. Whispering Hollow, Wellspring, Slippery
Bridge and Sunken Statue add potion bundles, removal/curse choices, escalating
damage and a sword that evolves after five elite victories. Potion rewards use
the complete ordinary Ironclad pool; curse transformations use all 18 native curse-pool cards. See the
[event pack evidence](docs/evidence/event_pack_2026_09_13.md). Dense Vegetation
adds event-triggered combat: Trudge On trades 8 HP for gold, while Rest
heals 30% maximum HP before a mandatory four-Wriggler fight, ordinary rewards
and map continuation. Sapphire Seed lets you heal and upgrade one
card, or give a card Sown for +1 energy on its first completed play each combat.
See [Sapphire Seed and enchantment evidence](docs/evidence/sapphire_seed_2026_09_13.md).
Byrdonis Nest is included in the generated pool: gain 7 maximum HP or take an egg, then
choose Hatch at a rest site to obtain Byrdpip and replace all eggs with Byrd Swoop.
Egg/Swoop transformations use the full 53-card single-player colorless pool.
See [Nest and hatch evidence](docs/evidence/byrdonis_nest_2026_09_13.md). Add `--ancient neow` for randomized two-positive/one-curse Neow offers and nested pickup choices;
omit it for the post-Ancient fixture start. The generated catalog now includes
all 21 normally Act-1-eligible events. Neow supports all 27 solo offers in the default catalog, including Kaleidoscope.
See [foreign acquisition evidence](docs/evidence/foreign_acquisition_2026_09_19.md) and
[events and Neow evidence](docs/evidence/events_neow_2026_09_14.md).
With the full Ironclad pool, the simple demo can lose before the boss. [Generated route details](docs/HEADLESS_ENGINE.md#generated-full-length-overgrowth-route).


Without reinstalling the console entry point, run
`PYTHONPATH=. python -m game.cli.headless_play` with the same arguments.

## Combat experiments

```bash
sts-demo
sts-train --policy compare --episodes 500 --eval-episodes 100
sts-train --config configs/double_dqn_overgrowth.json
sts-train --config configs/masked_ppo_overgrowth.json
sts-watch --policy heuristic --encounter slimes --deck ironclad_sequencing --seed 7
sts-oracle --encounter simple --seed 7
sts-benchmark-suite --dry-run
```

The default deck is `starter`; the optional `ironclad_sequencing` deck adds draw
and block/damage sequencing. Supported policies include random, heuristic,
Q-learning, DQN, Double DQN, Dueling Double DQN and masked PPO. Neural families
default to action-conditioned scoring, with opt-in `shared_enemy` architectures.

JSON configuration uses CLI names in snake_case; explicit CLI arguments override
the file. Prefer `output_dir` for a unique run folder containing the checkpoint,
resolved configuration and run metadata. Saved-agent tools accept a checkpoint
or its run directory. The legacy `save_agent` plus sidecars remains supported.

Use [experiment workflows](docs/EXPERIMENT_WORKFLOWS.md) for configuration,
sweeps, profiling, device choice, tracing and oracle/regret analysis.
[Benchmarks](docs/BENCHMARKS.md) and the [benchmark suite](docs/BENCHMARK_SUITE.md)
describe comparable fixed-seed and controlled-budget evaluations.
Each command's `--help` lists its complete options.

## Reduced headless experiments

```bash
sts-headless --help
sts-headless run --config configs/headless_smoke.json --output-root runs/headless-smoke
sts-headless benchmark --config configs/headless_smoke.json --output-root runs/headless-benchmark
sts-headless validate --output-root runs/headless-smoke --manifest-sha256 "<reported-manifest-sha256>"
```

Use a new output directory for every invocation and keep the printed manifest
hash separately. `run` requires one repetition; `benchmark` uses the configured
count. The smoke config has a small transition budget and is not a training run.
Help and pure headless commands do not import Torch or Gymnasium. Current CLI
input/cancellation hardening was validated on POSIX systems.

Artifacts preserve declared settings, trajectories and cancellation accounting.
They do not prove target-game fidelity or independently authenticate declared seeds.

The separate programmatic actor path uses `game.agents.headless_encoding`,
`game.data.headless_policy_dataset`, `game.agents.headless_candidate_policy`
and `game.training.headless_behavior_clone`. `train_headless_behavior_clone`
takes separated, manifest-anchored development/held-out sources, an accepted
backend manifest and a `BehaviorCloneConfig`. An optional new `output_root`
publishes a report, CPU checkpoint and completion marker; cancellation does not
publish an accepted artifact. Keep the returned report and logical checkpoint
hashes for `load_behavior_clone_artifact`. This smoke establishes plumbing on
structural data, not strategic strength or a new `sts-train` policy.
[Headless actor guide](docs/HEADLESS_ACTOR.md) links the source, schema and evidence.

## Live integration

Read [current status](docs/STATUS.md) and the
[live development guide](docs/LIVE_DEVELOPMENT.md) before selecting a component
or preparing a live test. The [unified bridge](bridge/Sts2AgentBridge/README.md)
packages all supported capabilities in one mod, with one client and development
checker. The [unified module smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md)
demonstrated representative combat, reward, map, shop, card, item and event paths,
with recorded setup assistance and remaining limits. Generalized transform input
also has focused native fixtures. Complete autonomous runs remain an open target.

## Project layout and documentation

| Location | Purpose |
| --- | --- |
| `game/headless/` | Canonical game rules, content, combat, persistent state and private continuation |
| `game/simulation/` | Combat research compatibility, observations, encoding, shaping and factories |
| `game/agents/`, `game/training/` | Policies, persistence, collectors and training |
| `game/contracts/`, `game/backends/`, `game/data/` | Full-game interfaces, reduced backend and artifacts |
| `game/analysis/`, `game/cli/` | Evaluation, inspection and installed commands |
| `bridge/Sts2AgentBridge/` | One production bridge, shared capability modules and focused checks |
| `configs/`, `tests/`, `manifests/game-builds/` | Experiments, regression coverage and pinned build identities |

Use canonical subpackage imports and installed `sts-*` commands; there are no
flat-module aliases or root CLI wrappers.

[Documentation index](docs/README.md) · [Roadmap](ROADMAP.md) ·
[Decisions](DECISIONS.md) · [Combat context](docs/PROJECT_CONTEXT.md)
