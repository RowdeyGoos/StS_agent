# Roadmap

Updated 2026-09-13. This file owns priorities; [current status](docs/STATUS.md)
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

## Remaining generic interaction work

The [research map](docs/EVENT_INTERACTION_MAP.md#interaction-families-and-concrete-blockers)
owns the event-to-family matrix and named acceptance candidates. Its concrete gaps
now require concrete callers for broader deck changes, resume-time card/selector
rewards and multiple independent children within one callback. The current batch
implements shop pickup selectors, full-inventory event policies, the initial
Fake Merchant Foul Potion fight and The Architect’s terminal progression. Plan shared capabilities from those dependencies, not event-name rules.

Keep representative held-out/live coverage for implemented families separate from
new implementation. Variable upgrades, true native cancellation, enchantment
stacking/replacement and unallocated-holder mechanisms need a concrete caller or
setup before becoming priorities. Claws and Sea Glass establish optional selection
through ancient pickup paths; these optional selectors have zero/partial/full live acceptance. They do not establish variable-count upgrades.

## Headless and learning direction

Keep the reduced backend and actor pipeline usable while improving fidelity of
named mechanics against the pinned game. The accepted cloning smoke proves
training/artifact plumbing on structural data; scale training when the relevant
rules and useful evaluation cases justify it.

The [headless full-game backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md) breaks
the remaining simulation work into selectable tasks with dependencies and acceptance
cases. Start with a pinned mechanic/reference case and one persistent gameplay slice
(for example HF-13, one executable card upgrade), then full-length reduced-content
runs, complete reachable Ironclad A0 content, and target-difficulty coverage. This
headless sequence does not reorder the live-bridge priorities above.

Retain these research priorities as evidence-driven options:

- compare action-conditioned and shared-enemy models on matched seeds/budgets;
- integrate semantic card records with an explicit representation/retraining boundary;
- add deterministic mixed-deck training after establishing per-deck baselines;
- use trace/oracle mistakes to choose mechanics, observation or training changes;
- extend encounter/status/card coverage where it improves the research benchmark.

Avoid more algorithms, content volume or training infrastructure without an
identified bottleneck or evaluation question.

## Long-term destination

Build one faithful reduced-content full-run environment, then stronger policy/value
models and optional tactical/strategic search over shared legal candidates.
Expand content and certify performance under the pinned target, public-information
boundary and declared compute budget. See the
[long-term architecture](docs/LONG_TERM_ARCHITECTURE_ROADMAP.md) for design detail.

Update this file when priorities change, not after every test run. For substantial
features, use available phase timings to check whether the streamlined process
reduces time to usable behavior without increasing regressions.
