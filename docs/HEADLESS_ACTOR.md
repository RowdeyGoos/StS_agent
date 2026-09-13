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

The [full-game implementation backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md)
records the dated assessment, dependencies, acceptance cases and remaining tasks.

The [actor-ready ledger](archive/phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md)
records the accepted encoder, dataset, candidate-policy and cloning work. Its
packet chronology and separate elite live attempt are historical. Read the
affected source and focused tests for a change; do not restart the completed
execution plan or use its old combined test count as a new acceptance gate.

Improve named mechanics against the pinned game before treating larger training
runs as evidence of useful play. [Roadmap](../ROADMAP.md#headless-and-learning-direction)
owns priorities, and [AGENTS.md](../AGENTS.md) owns proportionate validation.

## First card-upgrade profile

`CombatV0Backend(card_profile="strike_upgrade_v1")` supports ordinary Strike+
at 9 damage and 1 energy. The default backend still uses the original reduced
rules and rejects upgraded cards. The opt-in profile has distinct content, rules,
backend and projection identities; snapshot restore requires the same profile.
See the [pinned source check](evidence/strike_upgrade_2026_09_13.md) for evidence
and limits. Other card upgrades remain unsupported.

The current entry point is programmatic. Select one persistent instance at an
idle, living combat boundary, preview it, then upgrade it without changing its ID:

```python
from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.engine.card_upgrades import preview_card_upgrade, upgrade_persistent_card
from game.engine.headless_state import WorldState

backend = CombatV0Backend(card_profile="strike_upgrade_v1")
manifest = backend.manifest()
world = WorldState.create(
    seed=43, current_hp=80, max_hp=80, gold=0,
    deck_definition_ids=("strike", "strike", "defend"),
    map_node_definitions=(),
    content_fingerprint=manifest.content_fingerprint,
    rules_fingerprint=manifest.rules_fingerprint,
)
target_id = world.master_deck[0].instance_id
preview = preview_card_upgrade(world, target_id)  # cost=1, base_damage=9
upgrade_persistent_card(world, target_id)
launch = world.create_combat_launch("simple__starter")
decision = backend.reset(launch)
```

Use the existing bound candidate requests to play. On completion,
`world.apply_combat_resolution(launch, backend.resolution)` applies combat HP;
the next launch retains the permanent upgraded deck. For world snapshots, build
`WorldSnapshotCodec` with this manifest's content/rules fingerprints. Restore
combat snapshots into another backend constructed with the same card profile.

The public `headless_v0` card record and actor encoder already distinguish the
upgraded flag. Private instance IDs remain outside policy views. The optional
legacy combat encoder adds a `Strike+` name and has different dimensions from
legacy checkpoints. The reduced run composer, collector, rest-site choices and
training artifact acceptance have not been extended to this profile. Their
integration is separate backlog work; this slice establishes card execution,
persistence and replay, not full-run or native combat fidelity.
