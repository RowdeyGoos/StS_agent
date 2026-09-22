# Roadmap

Updated 2026-09-13. This file owns priorities; [current status](docs/STATUS.md)
owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

1. **Add custom screens first within generic event coverage.** The user selected
   custom screens as the next priority. Fake Merchant's inventory open, relic
   purchase, close and map path and Crystal Sphere's cell reveals, earned rewards
   and map exit are implemented. Crystal Sphere’s Uncover Future/gold/map path
   passed live, including completed-overlay cleanup. Fake Merchant’s inventory/two-purchase/leave path and
   Crystal Sphere Payment Plan also passed in one game process. Additional reward
   variants retain narrower evidence.
   Trial’s abandon popup is implemented offline with cancellation and explicitly
   confirmed terminal abandonment. Live coverage is still open.
   Hidden sphere item models remain private; no strategic-quality claim is made.
2. **Extend remaining pickup children after representative event coverage.**
   Battleworn Dummy training expiry and victory/potion resumption, Dense
   Vegetation combat, Lantern Key special-card rewards and Punch Off potion/relic
   rewards now passed through map return. The multi-case batch is complete and
   cleanup is verified. The checkout
   supports combat/rewards/map, callback-verified resumption, extra special-card
   and potion/relic rewards, terminal potion policies and known capacity growth.
   [Current status](docs/STATUS.md) owns exact implementation limits and pending
   live cases. Next, identify a concrete shop pickup selector
   or resume-time card reward, then broader selector composition and terminal
   dependencies. Use a concrete branch and observable outcome for each increment,
   reusing matching accepted evidence.
3. **Compose supported interactions into longer live runs after event coverage.**
   The combined batch covers Neow's Fury two-card and zero-card choices,
   resumption of combat after those choices, both reward policies, event/map
   handoff and an allocated off-screen
   single upgrade. Reuse the
   [combined batch](docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) and
   [unified smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md).
   Then test remaining handoffs and elite continuation. Use generalized
   transformation in useful play; do not repeat the card16 geometry experiment.
   Keep run-completion, branch coverage and strategic-quality claims separate.

Allocated off-screen transformation and single-upgrade holders each have a
representative live result. Further tests should address new behavior, such as
multi-upgrade or unallocated cards, rather than repeating their geometry checks.

## Remaining generic interaction work

The [research map](docs/EVENT_INTERACTION_MAP.md#interaction-families-and-concrete-blockers)
owns the event-to-family matrix and named acceptance candidates. Its concrete gaps
include broader deck changes after selectors and other pre-selector mutations, broader pickup
composition, resume-time selectors/card rewards, repeated/nested pickup selectors,
Fake Merchant combat and The Architect’s terminal progression. Plan shared capabilities from those dependencies, not event-name rules.

Keep representative held-out/live coverage for implemented families separate from
new implementation. Variable upgrades, true native cancellation, enchantment
stacking/replacement and unallocated-holder mechanisms need a concrete caller or
setup before becoming priorities. Claws and Sea Glass establish optional selection
through ancient pickup paths; these optional selectors have zero/partial/full live acceptance. They do not establish variable-count upgrades.

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

Next implement HF-44: sufficient public full-run observations, then encoding,
datasets and agent execution in HF-45–47. Establish faithful public inputs before
selecting training algorithms or investing in search infrastructure.

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
