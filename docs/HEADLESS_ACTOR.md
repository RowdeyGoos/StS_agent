# Reduced headless actor

The headless backend and actor pipeline support deterministic structural
experiments. They establish interface, dataset and training plumbing; they do
not establish target-game fidelity, learned live play or strategic strength.
Use the [project README](../README.md#reduced-headless-experiments) for CLI commands.

## Code and contracts

| Location | Responsibility |
| --- | --- |
| [Public encoder](../game/agents/headless_encoding.py) | Public decision and legal-candidate representation |
| [Accepted schema](research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json) | Encoding contract; retained at its existing path for executable consumers |
| [Policy dataset](../game/data/headless_policy_dataset.py) | Trusted examples with accepted artifact provenance |
| [Candidate policy](../game/agents/headless_candidate_policy.py) | Masked variable-candidate scoring and persistence |
| [Behavior cloning](../game/training/headless_behavior_clone.py) | Deterministic CPU training smoke and artifact publication/load |

Keep privileged backend state outside actor inputs. Preserve legal masks,
candidate identities and deterministic behavior. Training accepts separated,
manifest-anchored development and held-out sources plus an accepted backend
manifest and `BehaviorCloneConfig`. Preserve report and logical checkpoint hashes
when publishing/loading an artifact; cancellation does not publish an accepted
artifact. This is a programmatic path, not an additional `sts-train` policy.

## Evidence and development

The [actor-ready ledger](archive/phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md)
records the accepted encoder, dataset, candidate-policy and cloning work. Its
packet chronology and separate elite live attempt are historical. Read the
affected source and focused tests for a change; do not restart the completed
execution plan or use its old combined test count as a new acceptance gate.

Improve named mechanics against the pinned game before treating larger training
runs as evidence of useful play. [Roadmap](../ROADMAP.md#headless-and-learning-direction)
owns priorities, and [AGENTS.md](../AGENTS.md) owns proportionate validation.
