# Documentation index

Read [AGENTS.md](../AGENTS.md), then only the material needed for the task.
Current workflow supersedes procedural checklists in historical plans. Exact
artifact contracts, hashes and past evidence remain attributable to their version.

## Maintained guides

| Question | Source of truth |
| --- | --- |
| What is this project; how do I run it? | [README](../README.md) |
| How should a session work? | [AGENTS](../AGENTS.md) |
| What is implemented and demonstrated? | [Current status](PHASE_1_CURRENT_STATUS.md) |
| What comes next? | [Roadmap](../ROADMAP.md) |
| Why these architectural choices? | [Current decisions](../DECISIONS.md) |
| How does the combat research subsystem work? | [Project context](PROJECT_CONTEXT.md) |
| How do I train, profile or compare agents? | [Experiment workflows](EXPERIMENT_WORKFLOWS.md), [benchmarks](BENCHMARKS.md), [benchmark suite](BENCHMARK_SUITE.md) |
| How do I develop and test the live bridge? | [Live development](LIVE_DEVELOPMENT.md) |
| How should delegated work be organized? | [Multi-agent guide](MULTI_AGENT_EXECUTION.md), only when needed |
| What are the generic event architecture and next acceptance case? | [Generic handler plan](PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md) |
| What is the full-game destination? | Relevant sections of [long-term architecture](LONG_TERM_ARCHITECTURE_ROADMAP.md) and [target charter](PHASE_0_TARGET_CHARTER.md) |

The old [Astra handoff](PHASE_1_ASTRA_HANDOFF.md) is a navigation pointer, not
another status log. Keep operational state and latest evidence in current status.

## Component references

- Combat: [agent flow](AGENT_FLOW.md), [card representation](CARD_REPRESENTATION.md),
  [Ironclad cards](IRONCLAD_CARDS.md) and [Overgrowth hard pool](OVERGROWTH_HARD_V1.md).
- Headless actor: [accepted schema](research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json)
  and [actor-ready results](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md). The
  [completed execution plan](PHASE_1_ACTOR_READY_EXECUTION_PLAN.md) is an interface
  reference for affected consumers, not an active dispatch graph.
- Generic events: [coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md),
  [G7 semantics](PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), [G7 results](research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md),
  [v10 direct-selection contract](PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md)
  and [live result](research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md).
- Live bridge: [current build and component guide](../bridge/Sts2AgentBridge/README.md)
  and [historical release lookup](../bridge/Sts2AgentBridge/releases/history/README.md).
- Build identity: [manifest guide](../manifests/game-builds/README.md).
- Explicit profile work only: [live guide's user-data boundary](LIVE_DEVELOPMENT.md#user-data-boundary)
  routes to the exact preserved request/result before access.

## Historical references

Historical `PHASE_0_*` requests, completed `PHASE_1_*` plans and
`research/*ACCEPTANCE*` ledgers stay at stable paths because links, build
verification or evidence may depend on them. They are not mandatory startup
reading, current authorization, or instructions to repeat completed experiments.

The [earlier decision log](archive/DECISIONS_2026_09_08.md) preserves detailed
rationale and original decision IDs. Dated statuses and process prescriptions in
it are historical. Superseded overview text is recoverable in Git before this
cleanup, at `4f0c9ed`; do not duplicate it in new handoff files.

Maintain the guide that owns the changed fact. Record a new experiment once in its
acceptance ledger and link it from current status; update priorities or decisions
only if they actually changed.
