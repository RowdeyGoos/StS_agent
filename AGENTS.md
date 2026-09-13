# Working guide

Use this guide for every session. The user-approved workflow below (2026-09-08)
supersedes procedural requirements in older plans, handoffs and packet briefs.
Historical contracts still describe their exact artifact's semantics and evidence;
do not falsify hashes, bypass runtime safeguards or broaden user-data access.

## Start with the task

1. Check `git status --short --branch` and recent commits. Work in the user's
   current checkout; never switch to a hardcoded historical worktree. Main
   contains the integrated work as of this update.
2. Read the [README](README.md) overview and only the reference for your task:

   | Task | Read next |
   | --- | --- |
   | Live bridge or generic events | [Current status](docs/STATUS.md), then relevant source/contract; [live guide](docs/LIVE_DEVELOPMENT.md) before build/install/live work |
   | Headless game rules or architecture | [Headless engine](docs/HEADLESS_ENGINE.md), affected `game/headless/` source and tests |
   | Combat simulator or RL | Relevant sections of [project context](docs/PROJECT_CONTEXT.md), affected source and tests |
   | Headless actor/data | [Headless actor guide](docs/HEADLESS_ACTOR.md), then affected source/schema and tests |
   | Architecture or priorities | [Decisions](DECISIONS.md) and [roadmap](ROADMAP.md) |
   | Documentation | The document and its direct references |

3. Use the [documentation index](docs/README.md) when more context is needed.
   Do not recursively read all linked documents or completed phase plans.
   Search historical rationale only for a specific unresolved question.

## Default development loop

1. State the useful outcome and smallest observable acceptance case. For native
   behavior, identify a representative game interaction before building a large
   feature; label speculative capability work explicitly.
2. Keep one owner responsible through implementation, packaging and validation.
   Prefer a coherent end-to-end change using existing mechanisms.
3. Resolve uncertain assumptions with a narrow source inspection or controlled
   experiment early. Do not expand infrastructure to avoid testing the assumption.
4. Run focused checks, fix concrete failures, and perform the relevant final
   validation once the change is stable.
5. Finish the authorized feedback loop. Do not routinely stop at "implemented,
   needs packaging" when packaging/testing was requested. If user readiness is
   needed, prepare the build first and give one precise setup instruction.
6. Report behavior, evidence, remaining limits and next useful step concisely.
   For substantial work, record available elapsed times for implementation,
   review, validation, release preparation and user wait; do not invent missing
   timings or create a telemetry subsystem.

Reuse authorization already given. Ask only for genuinely missing scope, necessary
user readiness or actions outside that authority. Routine fixes, documentation,
local verification and implementation choices do not need repeated permission.

## Controlled experiments

- Answer the concrete capability question with the smallest safe test.
- Keep target identity, native legality, ownership, bounded execution, outcome
  verification and cleanup. Never retry an uncertain mutation.
- Distinguish prerequisites for safely acting from facts needed to broaden the
  conclusion. User-controlled setup or visual confirmation may establish an
  experiment's premise; record it without building a general proof mechanism.
- Example: select a known allocated off-screen card once and check its exact
  preview. Do not require clipping-parent detection or a viewport certificate.
  One successful setup does not prove every deck size or selector.
- If a test stops before exercising the feature, question the necessity of the
  blocking prerequisite before adding diagnostics or another release.
- Add bounded, useful failure categories at the relevant boundary. Tests of
  inert game objects cannot settle assumptions about the real game's behavior.

## Review and validation

| Change | Required validation |
| --- | --- |
| Documentation only | Diff, relevant links, factual consistency and any affected artifact bindings; no gameplay suite or live launch |
| Local behavior/fix using existing contracts | Focused regression and affected consumers; author review normally suffices |
| Live mutation, protocol, public information, RNG, persistence or cleanup semantics | Focused adversarial cases, one independent semantic review and relevant integration checks |
| Release | Changed behavior plus build/package/source identity and installation/cleanup checks; one final release gate |

Additional review must answer a distinct unresolved risk. Reviewers block concrete
correctness, compatibility or safety failures, not speculative improvements outside
the task. Use [multi-agent guidance](docs/MULTI_AGENT_EXECUTION.md) only when
delegation is permitted and would shorten the critical path.

Run targeted tests during corrections. Reuse trusted accepted evidence only when
the relevant transitive sources, tests, dependencies, toolchain and settings match.
A hash alone is not evidence that tests ran. Rerun affected checks after a relevant
change, failure or new concern. Do not repeat full candidate/frozen matrices merely
because a manifest, documentation or commit identity changed.

For broad Python integration, use the existing environment and run:

```bash
python3 -m compileall game tests
PYTHONPATH=. python3 -m pytest -q
```

Choose narrower paths for local changes. Build bridge fixtures in disposable
outputs; follow the selected release's actual build inputs and compatibility checks.

## Source and release discipline

Maintain **one production bridge**, `bridge/Sts2AgentBridge/apps/bridge/`.
Shared capability code lives in `components/`; the original public combat/reward/
map/room adapters remain in `src/`. New features extend these modules and the
shared router. Do not create another mod, listener, configuration tree, client,
package pipeline or source snapshot for a feature or test attempt.

Use the [bridge checker](bridge/Sts2AgentBridge/README.md) with `--component` for
focused development. One stable release builds and packages the combined bridge.
The checker derives the current package identity from that build; do not manually
repin several operational tools. Retain one current release manifest and evidence;
Git keeps earlier versions. The old successor sources remain in Git and original
identities in `releases/history/`, outside the current build graph.

Keep native modules exclusive through reconciliation and successful cleanup.
An uncertain action or failed disposal stops the host; never turn it into a clean
handoff. Keep release packages, source commit, manifest and evidence. Version
public interfaces for semantic changes, not test attempts. Never repin old
evidence or bypass a failing runtime safeguard.

## Invariants

- Python 3.10+; explicit seeded RNG; no new global mutable simulator state.
- Keep state serializable and structured observations separate from RL encoding.
- Preserve stable enemy slots, legal-action masks and the simple combat path.
- Keep canonical subpackage imports and installed `sts-*` commands; no flat aliases
  or root CLI wrappers.
- Implement game logic in `game/headless/`, which must not import adapters, public
  contracts, encoders or training. Game-content changes do not require projection
  or policy changes unless that consumer integration is explicitly in scope.
- Changes to supported observation/action adapters require checking `game/simulation/core.py`,
  `encoding.py`, `actions.py`, `action_features.py` and affected baselines,
  demo formatting and tests. Update only affected consumers.
- Preserve public/privileged separation and distinguish synthetic, released and
  live-demonstrated evidence. Full-game utility is run victory probability;
  combat-local HP reward shaping does not redefine it.
- Profile/save/history/Cloud access is outside ordinary development. Old
  one-shot approvals are not standing authority; see the [live guide](docs/LIVE_DEVELOPMENT.md).

## Documentation maintenance

Keep one source of truth per topic: README for usage, current status for capability
and latest operational evidence, roadmap for priorities, decisions for durable
choices, and acceptance ledgers for historical results. Update only documents whose
meaning changes. Do not copy campaign chronology into several overview files.

Keep current guides at the top of `docs/`, organized by topic rather than phase or
test attempt. Put substantial experiment results in `docs/evidence/`; move
completed plans, old reviews and superseded records to `docs/archive/`. Follow the
[documentation index](docs/README.md) and [archive policy](docs/archive/README.md).
Do not create a separate plan, review ledger, status page or handoff for every
correction. Routine validation belongs in the change summary.

Keep startup guidance short. Archived procedures are not a fresh-session task
queue. Preserve recorded hashes and original Git identities when moving evidence;
adjust navigation links without repinning historical results. Read exact original
bytes from the recorded Git revision when a historical contract requires them.
