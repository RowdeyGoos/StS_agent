# Roadmap

Updated 2026-09-08. This file owns priorities; [current status](docs/PHASE_1_CURRENT_STATUS.md)
owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

1. **Generalize the working direct transformation input.** Remove the latest
   experiment's card-16-only restriction in the maintained development path and
   expose all legal, allocated holders. Preserve exact identity, preview and
   completion checks. Do not reintroduce viewport/clipping proof or a ten-card
   workaround. The [generic handler plan](docs/PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md)
   defines the concrete acceptance case.
2. **Keep the consolidated source editable.** The 32 source snapshots and
   predecessor-checker chain have been removed. Use the affected current target,
   retain one shared implementation and reuse unchanged evidence. Consolidate
   remaining app-specific tooling only when it helps the feature being changed.
3. **Expand the next interaction that blocks useful play.** Establish a real
   representative caller first. Prioritize observed gaps over hypothetical
   capability combinations or another event-name allowlist.
4. **Compose supported interactions into longer live runs.** Test remaining
   handoffs, elite continuation and unsupported surfaces with targeted setups.
   Keep run-completion, branch coverage and strategic-quality claims separate.

The current off-screen capability question has been answered for an allocated
transform holder. A further live test should address new behavior, not repeat
that experiment to obtain a different geometric proof.

## Remaining generic interaction work

- Optional/zero-card selection and native cancellation.
- Variable-count upgrading where a real native early-completion path exists.
- Selecting cards outside the allocated holder set, including scrolling/rebinding.
- Multiple-item offer sets, repeated/custom interactions and event combat.
- Representative held-out and live coverage for implemented families.

Fixed/variable transformation support already exists offline; positive variable
counts still need a suitable live caller. Do not prioritize a variable-count live
test without finding one. Full details belong in the generic handler plan and
coverage matrix, not in another duplicate status table here.

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
