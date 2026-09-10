# Roadmap

Updated 2026-09-10. This file owns priorities; [current status](docs/STATUS.md)
owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

1. **Expand generic event interactions first.** The user identified event
   coverage as the current obstacle and prioritized it ahead of longer-run
   orchestration. Generic **single-card enchantment** now has live acceptance:
   Sapphire Seed Plant and Nourish, exact Sown effect and fresh actionable map.
   Keep extending the shared parent/child machinery from representative native
   interactions; do not add event-name admission rules.
2. **Validate event combat and extend resume-time children next.** The checkout
   supports non-resuming combat/rewards/map and callback-verified combat/event/map.
   Pending live cases are Dense Vegetation’s Fight page after Rest and Battleworn
   Dummy Setting2/training expiry. Exact initial-option selection is reusable
   through `--event-option`. Next implement interactive children during event
   resume (Setting1 potion offer or a Setting3 pickup selector), then extra combat
   rewards and full-inventory/nested pickups.
   The completed live batch now covers mixed card/item rewards, ancient options,
   Sea Glass and Claws zero/partial/full selection, card offers, bundles, inactive
   Punch Off/Nab and Pandora's Box results acknowledgment. These are no longer
   an untested feature queue; [current status](docs/STATUS.md) owns exact limits.
   Then address full-inventory/nested pickups, broader selector grant composition
   and custom/terminal dependencies. Use a concrete branch and observable outcome
   for each increment, reusing matching accepted evidence.
3. **Compose supported interactions into longer live runs after event coverage.**
   The combined batch covers Neow's Fury two-card and zero-card choices, combat
   resume, both reward policies, event/map handoff and an allocated off-screen
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
composition, resume-time children/extra-reward event combat, repeated/nested pickup selectors, and custom/terminal
surfaces. Plan shared capabilities from those dependencies, not event-name rules.

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
