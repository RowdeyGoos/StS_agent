# Coordinating delegated work

Read only when delegation is permitted by the current session and useful for the
task. [AGENTS.md](../AGENTS.md) owns review, validation and authorization policy.
This guide replaces the former packet-heavy operating model.

## Choose useful parallelism

Default to one owner of the complete change. Delegate an independently useful
piece only when its interface is clear and review/integration will not take
longer than doing it locally. Parallelize independent features, a specific source
investigation, or a distinct review question; do not fragment a short sequential
fix into contract, implementation, checker, provenance and review lanes.

For risky changes, use one independent reviewer of the aggregate semantics.
Add specialists only for different unresolved risks. Do not have every participant
re-review every other participant or recreate the same test evidence.
Documentation-only work does not need a review agent.

## A short brief is enough

Give each delegated task:

- the intended result and relevant inputs;
- exact writable files, read-only dependencies and one active owner;
- the contract it must preserve and concrete acceptance case;
- the expected handoff: changed files, checks performed, blockers and limitations.

Keep this in the task message or one working note. Do not create a permanent
contract document, ledger and separate branch for every small task. A shared
semantic change needs a short producer/consumer agreement before dependent edits.

## Ownership and integration

Use an isolated worktree when writers would conflict or rollback needs isolation.
A shared checkout is fine for disjoint files with explicit ownership. Preserve
existing user changes. One owner integrates dependent work in order and resolves
contract disagreements before consumers continue.

Do not impose a worker target. Only start work the coordinator can review and
integrate promptly. Follow the user's current model preferences; old packet model
assignments are historical.

The implementer fixes concrete review findings and reruns affected checks. The
reviewer then checks the correction, rather than reopening unrelated accepted
scope. The owner runs the agreed aggregate once on the final candidate and
records exactly which earlier results were reused.

A reviewer identifies a blocking behavior, its trigger, impact and evidence.
Useful optional refactors and speculative edge cases go to a follow-up only if
they matter; they do not silently enlarge acceptance criteria.

## Handoff and communication

Return one integrated result per owner. Include source/commit identity when useful,
meaningful test results, evidence level and any required next action. Do not
equate a passing mock with successful native behavior.

Use completion messages or bounded waits instead of repeated polling. User-facing
updates explain outcomes and blockers; do not expose an internal packet transcript.
Carry through authorized integration and release work without asking the user to
approve routine corrections or coordinate the agents.

Record available phase timings in the normal result for substantial work. Unknown
metrics stay unknown. Measure whether delegation shortens delivery, not how many
agents were kept busy.
