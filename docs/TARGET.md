# Full-game target

The goal is an autonomous standard single-player Ironclad agent that optimizes
complete-run victory probability. The first functional milestone is reliable
Ascension 0 completion. Eventual certification targets the highest standard
Ironclad difficulty in the pinned build; its exact level must be verified in-game.
The project has not yet earned a complete autonomous, strong or near-optimal claim.

## Scope and information

- The pinned target is Slay the Spire 2 `v0.107.1`, Steam main build `23811903`,
  depot `2868842`, manifest `8653035385353091849`; the
  [build manifest](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
  owns its exact identity.
- Use base gameplay and one declared observation/control bridge. The target
  includes every decision family reachable in the declared profile and mode.
- Actor, memory and planner inputs contain player-visible information, public
  history, independently knowable rules and authoritative legal candidates.
  Keep hidden draw order, future outcomes and privileged diagnostic fields separate.
- The run seed, seed-derived features and true RNG state are excluded from actor
  input. Evaluation infrastructure may retain seeds for reproducibility and pairing.
- Report policy-only and planner-enhanced inference separately under declared
  per-decision and whole-run compute budgets. Combat-local reward shaping does
  not redefine the full-game objective.
- Cooperative multiplayer and alternate modes are outside the project scope.
- Other characters, gameplay mods, cross-patch comparisons, save-scumming and
  manual intervention in scored runs are outside the initial Ironclad target.
  Controlled development setups are separate from scored runs.
- Headless campaign acceptance may use an explicitly declared boosted starting
  HP/max HP in both native and Python runs. Normal-HP victory by a test policy is
  not a simulator completion requirement. Actual damage, healing, HP thresholds,
  death/revival and all other rules remain enabled; focused boundary tests cover
  behavior that a high-HP campaign may not encounter. Agent evaluation retains
  ordinary gameplay conditions and its separate victory-probability objective.

## Unresolved evaluation requirements

These are requirements for the relevant benchmark or certification campaign,
not prerequisites for every feature change:

| Requirement | Remaining definition or evidence |
| --- | --- |
| Reproducible profile | Exact unlock/settings manifest, construction or restoration method, verification and reset procedure |
| Evaluation population | Sealed development/held-out seed and state registries, split sizes and access rules |
| Inference budget | Named certification mode and numerical policy/search limits |
| Success criteria | Numerical A0 reliability, strong-agent and near-optimal thresholds; practical margins, subgroup/audit criteria and prospective sample-size/power rules |
| Comparisons | Versioned reference agents, paired runs and preregistered failure/exclusion handling |
| Research baseline | Deliberately selected immutable `combat_v0` package; exploratory benchmark outputs are not that baseline |
| Fidelity | Named conformance evidence for the fast backend; structural headless fixtures do not establish target-game parity |

“Near optimal” would be a bounded operational claim under those declared
conditions, not a proof of global optimality. Preserve natural run outcomes and
report infrastructure failures and exclusions under the campaign's frozen policy.

Profile filesystem work requires explicit scope under the
[live guide](LIVE_DEVELOPMENT.md#user-data-boundary). The earlier baseline probe
stopped before target-content access; its records authorize no corrected rerun.

The [original charter](archive/phase-0/PHASE_0_TARGET_CHARTER.md) retains detailed
evaluation design and decision history. [Long-term architecture](LONG_TERM_ARCHITECTURE_ROADMAP.md)
describes the research destination; [roadmap](../ROADMAP.md) owns current priorities.
