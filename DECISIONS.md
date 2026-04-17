# DECISIONS.md

This file records the main architectural decisions behind the current simulator. It is intentionally lightweight: the goal is to help future contributors and coding sessions understand why the code looks the way it does.

When a change alters core assumptions about observations, actions, rewards, encounter structure, or training defaults, update this file.

## D1. Keep Structured Observations Separate From RL Encoding

### Context

The simulator needs to be readable for debugging and tests, but RL agents want fixed-width numeric inputs.

### Decision

- `CombatEnv.get_observation()` returns a structured dict that is easy for humans and tests to inspect.
- `ObservationEncoder` in `game/encoding.py` converts that dict into a fixed-width numeric vector and handles discrete action encoding.

### Why

- keeps game logic independent from a specific model architecture
- makes debugging much easier than working only with vectors
- allows the RL representation to evolve without forcing a rewrite of the environment API

## D2. Use Stable Enemy Slots In Multi-Enemy Encounters

### Context

Once multi-enemy encounters were added, the environment needed targetable enemies and fixed-width observations.

### Decision

- `CombatEnv` stores `self.enemies` as a stable list of slots for the full combat.
- Dead enemies are not removed from the list mid-combat.
- Encoded observations include a fixed number of enemy slots, each with an `alive` feature.

### Why

- target indices stay stable across the episode
- RL action encoding does not shift when one enemy dies
- fixed-width observation encoding stays simple and predictable

### Consequence

Callers should filter on living enemies rather than assuming every slot is active.

## D3. Use A Fixed Discrete Action Space With Legal-Action Masking

### Context

RL methods in this repo currently assume a small discrete action space, but combat legality changes every turn.

### Decision

- tuple actions remain the readable source API:
  - `("play", hand_index)`
  - `("play", hand_index, target_index)`
  - `("end_turn",)`
- RL agents use a fixed discrete action space from `ObservationEncoder`
- `CombatEnv.get_action_mask()` is the authoritative legality signal

### Why

- easy to plug into DQN-style methods
- keeps invalid-action handling explicit
- preserves a clean debugging API while still supporting neural agents

## D4. Reward Should Favor Winning While Preserving HP

### Context

A pure win/loss reward made many policies look similar even when one survived comfortably and another barely scraped by.

### Decision

Reward is:

- `+1` on win
- `-1` on loss
- minus normalized player HP lost during the step

### Why

- encourages policies that win cleanly, not just eventually
- gives denser learning signal than terminal rewards alone
- lines up with the intended objective for this project: win with as much HP left as possible

## D5. Keep A Very Small "Simple" Encounter Alongside Richer Encounter Sets

### Context

The project needs richer combat for RL, but also a tiny stable environment for debugging and regression tests.

### Decision

- retain the single deterministic `SimpleEnemy` path
- add richer encounter pools, such as `overgrowth_easy`, without removing the simple mode

### Why

- faster smoke tests
- easier debugging of core mechanics
- avoids forcing every test or experiment into the more complex multi-enemy path

## D6. Prefer Explicit Combat Rules Over A Premature Generic Event System

### Context

The simulator may eventually need many statuses, relics, and triggered effects, but the current scope is still modest.

### Decision

- keep combat rules explicit in the relevant modules for now
- statuses are modeled in `game/status.py` with simple helper logic
- enemy and card effects directly call the small set of game-state methods they need

### Why

- easier to reason about correctness
- less abstraction overhead while the ruleset is still changing quickly
- better fit for a research playground than a full engine architecture

### Consequence

When adding more complex mechanics later, it may become worth introducing a more generic hook/event model. We are not there yet.

## D7. DQN And Tabular Q-Learning Need Different Defaults

### Context

A shared learning-rate default worked poorly once neural agents were added. The value was reasonable for tabular Q-learning but too large for DQN.

### Decision

- `train.py` keeps separate defaults for tabular and DQN-family learning rates
- DQN and Double DQN restore the best evaluation checkpoint before the final evaluation by default

### Why

- avoids avoidable late-training collapse
- makes CLI defaults safer
- gives more trustworthy final evaluation summaries

## D8. Keep Python 3.10 Compatibility

### Context

The project currently targets Python 3.10+.

### Decision

- avoid syntax that requires newer Python versions unless the version floor is intentionally raised
- prefer broadly compatible language features in user-facing scripts and library code

### Why

- lowers setup friction
- keeps the project usable on more machines
- prevents subtle issues such as Python-3.12-only f-string expression syntax

## D9. Use Overgrowth Easy As The First Multi-Enemy Benchmark

### Context

The project needed a richer encounter pool than the original single enemy, but not the full complexity of a complete run structure.

### Decision

- implement the first-three-fights pool from Slay the Spire 2 Overgrowth as the first richer benchmark set
- support both solo fights and the 3-slime encounter

### Why

- introduces multi-enemy targeting and more diverse enemy behavior
- still small enough to debug and train on quickly
- a better intermediate step than jumping straight to relics, potions, or full map progression
