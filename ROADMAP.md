# Roadmap

Updated 2026-09-09. This file owns priorities; [current status](docs/STATUS.md)
owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

1. **Compose supported interactions into longer live runs.** The combined batch
   now covers Neow's Fury two-card and zero-card choices, combat resume, both
   reward policies, event/map handoff and an allocated off-screen single upgrade.
   Test remaining handoffs, elite continuation and unsupported surfaces with
   targeted setups. Keep run-completion, branch coverage and strategic-quality
   claims separate. Reuse the
   [combined batch](docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) and
   [unified smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md)
   evidence for unchanged paths.
2. **Use the generalized transformation path in useful play.** All eligible,
   allocated holders use direct input, with identity/preview/completion checks.
   The [generic handler guide](docs/GENERIC_EVENTS.md) describes its evidence and
   remaining native questions. Do not repeat the card16 experiment merely to
   obtain another geometric proof.
3. **Expand the next interaction that blocks useful play.** Establish a real
   representative caller first. Prioritize observed gaps over hypothetical
   capability combinations or another event-name allowlist.

Allocated off-screen transformation and single-upgrade holders each have a
representative live result. Further tests should address new behavior, such as
multi-upgrade or unallocated cards, rather than repeating their geometry checks.

## Remaining generic interaction work

- Generic-event optional/zero-card selection and native cancellation. Combat
  discard/exhaust grid choices have a separate implementation; Neow's Fury zero
  and two-card discard choices now have live evidence.
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
