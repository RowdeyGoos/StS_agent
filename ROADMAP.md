# Roadmap

Priorities set 2026-09-13; documentation clarified 2026-09-19. This file owns priorities; [current status](docs/STATUS.md)
owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

1. **Resolve Architect admission before another ending retest.** Native final-act
   setup now reaches its untouched Proceed, but the bridge returns
   `unsupported_state` before dispatch. Identify the exact rejected predicate,
   preserve native ownership and task guards, then verify the complete win path.
   The implemented terminal task chain has offline coverage; it has not passed live.
2. **Finish representative coverage of remaining pickup and selector variants.**
   Custom screens, Trial abandonment Cancel/Confirm, event combat/reward/map paths,
   Dummy victory with automatic upgrades, terminal potion policies and assisted
   Fake Merchant seven-relic collection now have live results. Remaining targets
   include shop passive/Potion Belt purchases and pickup selectors, capacity-first
   terminal/event/resume rewards, Sphere tool/reward variants, and a true multi-card
   upgrade selector. Dummy’s automatic upgrades do not establish selector coverage.
   The original Merchant reward list can exceed the eight-entry reader limit;
   handling that full screen is distinct from the demonstrated assisted collection.
   Choose a concrete native caller and observable outcome before extending a mechanism.
   [Current status](docs/STATUS.md) owns exact evidence and practical limits.
3. **Compose supported interactions into longer live runs after event coverage.**
   Reuse the [multi-case results](docs/evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md),
   [combined batch](docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) and
   [unified smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md).
   Test remaining handoffs and elite continuation, keeping run completion,
   branch coverage and strategic quality as separate claims. Use generalized
   transformation in useful play; do not repeat the card16 geometry experiment.

Allocated off-screen transformation and single-upgrade holders each have a
representative live result. Further tests should address new behavior, such as
multi-upgrade or unallocated cards, rather than repeating their geometry checks.

## Scope of further bridge implementation

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns the missing-feature list, separately from implemented capabilities awaiting
live coverage. The confirmed gaps include rest selector cancellation,
additional Dig pickup follow-ups and wider reward-screen bounds. Unsupported selector/pickup shapes without a concrete caller
are explicitly separated from that list; multi-card Smith is not a native gameplay
requirement in the pinned assembly. This documentation cleanup does not
promote every unsupported variant into an immediate priority.

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
