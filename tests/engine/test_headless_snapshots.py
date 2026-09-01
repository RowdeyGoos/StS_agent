"""Exact continuation and compatibility tests for private world snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    CombatOutcome,
    NodeKind,
    PublicObservation,
)
from game.engine.headless_state import (
    COMBAT_LAUNCH_STREAM,
    EVENT_EFFECT_STREAM,
    REWARD_OFFER_STREAM,
    WORLD_SEMANTIC_KEY_VERSION,
    WORLD_STATE_FINGERPRINT,
    AutomaticTransition,
    CombatResolution,
    PendingDecision,
    StateValidationError,
    WorldState,
    canonical_private_json,
)
from game.engine.snapshots import (
    PRIVATE_SNAPSHOT_SCHEMA,
    PRIVATE_SNAPSHOT_VERSION,
    PrivateWorldSnapshot,
    SnapshotValidationError,
    WorldSnapshotCodec,
)


CONTENT_FINGERPRINT = "a" * 64
RULES_FINGERPRINT = "b" * 64


def _forged_semantic_key(payload: dict) -> str:
    encoded = (
        f"{WORLD_SEMANTIC_KEY_VERSION}\0{canonical_private_json(payload)}"
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _world(seed: int = 123) -> WorldState:
    world = WorldState.create(
        seed=seed,
        current_hp=71,
        max_hp=80,
        gold=42,
        deck_definition_ids=("strike", "defend", "bash"),
        map_node_definitions=(
            ("floor_01_combat", NodeKind.COMBAT),
            ("floor_02_rest", NodeKind.REST),
        ),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=RULES_FINGERPRINT,
    )
    world.current_node_id = world.map_nodes[0].instance_id
    world.node_history = (world.map_nodes[0].instance_id,)
    world.pending_decision = PendingDecision(
        "combat_action",
        3,
        {"hidden_combat_token": "internal.0003"},
    )
    world.automatic_queue = (
        AutomaticTransition("resolve_room", {"queued": True}),
    )
    return world


def _codec(
    *,
    content_fingerprint: str = CONTENT_FINGERPRINT,
    rules_fingerprint: str = RULES_FINGERPRINT,
) -> WorldSnapshotCodec:
    return WorldSnapshotCodec(content_fingerprint, rules_fingerprint)


def test_private_snapshot_json_round_trip_is_exact_and_immutable() -> None:
    world = _world()
    world.rng.randint(COMBAT_LAUNCH_STREAM, 0, 100)
    world.rng.choice(REWARD_OFFER_STREAM, ("strike", "defend"))
    codec = _codec()

    snapshot = codec.capture(world)
    encoded = snapshot.to_json()
    decoded = PrivateWorldSnapshot.from_json(encoded)
    restored = codec.restore(decoded)

    assert decoded == snapshot
    assert codec.capture(restored) == snapshot
    assert restored.to_private_dict() == world.to_private_dict()
    assert restored.semantic_key() == world.semantic_key() == snapshot.semantic_key
    assert json.loads(encoded) == snapshot.to_dict()
    with pytest.raises(TypeError):
        snapshot.payload["gold"] = 999


def test_restored_world_has_exact_rng_and_identity_continuation() -> None:
    original = _world(seed=984)
    original.rng.randint(COMBAT_LAUNCH_STREAM, 0, 10_000)
    original.rng.choice(REWARD_OFFER_STREAM, ("a", "b", "c"))
    original_values = [1, 2, 3, 4]
    original.rng.shuffle(EVENT_EFFECT_STREAM, original_values)
    restored = _codec().loads(_codec().dumps(original))

    assert restored.rng_stream_counters() == original.rng_stream_counters()
    assert restored.rng.randint(COMBAT_LAUNCH_STREAM, 0, 10_000) == (
        original.rng.randint(COMBAT_LAUNCH_STREAM, 0, 10_000)
    )
    assert restored.rng.choice(REWARD_OFFER_STREAM, ("a", "b", "c")) == (
        original.rng.choice(REWARD_OFFER_STREAM, ("a", "b", "c"))
    )
    restored_values = [5, 6, 7, 8]
    original_values = [5, 6, 7, 8]
    restored.rng.shuffle(EVENT_EFFECT_STREAM, restored_values)
    original.rng.shuffle(EVENT_EFFECT_STREAM, original_values)
    assert restored_values == original_values

    assert restored.add_card("iron_wave") == original.add_card("iron_wave")
    assert restored.add_map_node("floor_03_event", NodeKind.EVENT) == (
        original.add_map_node("floor_03_event", NodeKind.EVENT)
    )
    assert restored.to_private_dict() == original.to_private_dict()


def test_active_combat_launch_binding_restores_for_exact_continuation() -> None:
    world = _world(seed=661)
    launch = world.create_combat_launch("jaw_worm_v0")
    restored = _codec().restore(_codec().capture(world))
    forged_launch = replace(launch, combat_seed=launch.combat_seed ^ 1)

    assert restored.active_combat_launch_key == launch.semantic_key()
    assert restored.rng_stream_counters()["combat_launch"] == 1
    restored.validate_combat_launch(launch)
    with pytest.raises(StateValidationError, match="active issued launch"):
        restored.validate_combat_launch(forged_launch)
    with pytest.raises(StateValidationError, match="already active"):
        restored.create_combat_launch("jaw_worm_v0")

    resolution = CombatResolution(
        run_id=restored.run_id,
        launch_key=launch.semantic_key(),
        outcome=CombatOutcome.VICTORY,
        final_hp=64,
        replay_reference="replay.combat.restored",
    )
    restored.apply_combat_resolution(launch, resolution)
    assert restored.current_hp == 64
    assert restored.active_combat_launch_key is None
    assert restored.rng_stream_counters()["combat_launch"] == 1


def test_restored_stream_counters_are_exact_and_streams_remain_isolated() -> None:
    baseline = _world(seed=515)
    noisy = _world(seed=515)
    for _ in range(20):
        noisy.rng.choice(REWARD_OFFER_STREAM, ("x", "y"))
        values = [0, 1, 2]
        noisy.rng.shuffle(EVENT_EFFECT_STREAM, values)

    restored = _codec().restore(_codec().capture(noisy))
    expected = [baseline.rng.randint(COMBAT_LAUNCH_STREAM, 0, 1_000_000) for _ in range(6)]
    actual = [restored.rng.randint(COMBAT_LAUNCH_STREAM, 0, 1_000_000) for _ in range(6)]

    assert actual == expected
    assert restored.rng_stream_counters() == {
        "combat_launch": 6,
        "event_effect": 20,
        "reward_offer": 20,
    }
    assert noisy.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 20,
        "reward_offer": 20,
    }


@pytest.mark.parametrize(
    "attribute,bad_value,match",
    [
        ("contract_fingerprint", "0" * 64, "contract_fingerprint"),
        ("content_fingerprint", "1" * 64, "content_fingerprint"),
        ("rules_fingerprint", "2" * 64, "rules_fingerprint"),
        ("state_fingerprint", "3" * 64, "state_fingerprint"),
    ],
)
def test_incompatible_snapshot_fingerprints_reject(
    attribute: str,
    bad_value: str,
    match: str,
) -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    incompatible = replace(snapshot, **{attribute: bad_value})

    with pytest.raises(SnapshotValidationError, match=match):
        codec.restore(incompatible)


def test_codec_rejects_incompatible_contract_and_state_fingerprints() -> None:
    with pytest.raises(SnapshotValidationError, match="contract fingerprint"):
        WorldSnapshotCodec(
            CONTENT_FINGERPRINT,
            RULES_FINGERPRINT,
            contract_fingerprint="0" * 64,
        )
    with pytest.raises(SnapshotValidationError, match="state fingerprint"):
        WorldSnapshotCodec(
            CONTENT_FINGERPRINT,
            RULES_FINGERPRINT,
            state_fingerprint="0" * 64,
        )

    codec = _codec()
    assert codec.contract_fingerprint == CONTRACT_FINGERPRINT
    assert codec.state_fingerprint == WORLD_STATE_FINGERPRINT


def test_payload_tampering_rejects_by_semantic_key() -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    payload = deepcopy(snapshot.to_dict()["payload"])
    payload["gold"] += 1
    tampered = replace(snapshot, payload=payload)

    with pytest.raises(SnapshotValidationError, match="semantic key"):
        codec.restore(tampered)


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("content_fingerprint", "c" * 64),
        ("rules_fingerprint", "d" * 64),
    ],
)
def test_recomputed_semantic_key_cannot_forge_payload_fingerprints(
    field: str,
    bad_value: str,
) -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    payload = deepcopy(snapshot.to_dict()["payload"])
    payload[field] = bad_value
    forged_state = WorldState.from_private_dict(payload)
    forged = replace(
        snapshot,
        payload=payload,
        semantic_key=forged_state.semantic_key(),
    )

    with pytest.raises(SnapshotValidationError, match=f"payload {field}"):
        codec.restore(forged)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda allocator: allocator.__setitem__("run_id", None),
        lambda allocator: allocator.__setitem__("next_run_ordinal", 2),
    ],
)
def test_recomputed_semantic_key_cannot_forge_one_run_allocator(mutate) -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    payload = deepcopy(snapshot.to_dict()["payload"])
    mutate(payload["identity_allocator"])
    forged = replace(
        snapshot,
        payload=payload,
        semantic_key=_forged_semantic_key(payload),
    )

    with pytest.raises(SnapshotValidationError, match="payload"):
        codec.restore(forged)


def test_unhashable_current_node_id_is_translated_to_snapshot_validation_error() -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    payload = deepcopy(snapshot.to_dict()["payload"])
    payload["current_node_id"] = []
    forged = replace(
        snapshot,
        payload=payload,
        semantic_key=_forged_semantic_key(payload),
    )

    with pytest.raises(SnapshotValidationError, match="payload"):
        codec.restore(forged)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("schema", "other_world_v1"),
        lambda payload: payload.__setitem__("state_version", 2),
        lambda payload: payload.__setitem__("state_version", True),
        lambda payload: payload.__setitem__("unexpected", True),
        lambda payload: payload.__setitem__("master_deck", []),
        lambda payload: payload["identity_allocator"].__setitem__(
            "next_card_ordinal", 0
        ),
        lambda payload: payload["rng"].__setitem__("snapshot_version", 999),
    ],
)
def test_invalid_world_payload_rejects(mutate) -> None:
    codec = _codec()
    snapshot = codec.capture(_world())
    payload = deepcopy(snapshot.to_dict()["payload"])
    mutate(payload)

    with pytest.raises(SnapshotValidationError, match="payload"):
        codec.restore(replace(snapshot, payload=payload))


def test_snapshot_envelope_schema_and_versions_reject_strictly() -> None:
    snapshot = _codec().capture(_world())
    assert snapshot.snapshot_schema == PRIVATE_SNAPSHOT_SCHEMA
    assert snapshot.snapshot_version == PRIVATE_SNAPSHOT_VERSION == 1

    for field, value in (
        ("snapshot_schema", "other_snapshot_v1"),
        ("snapshot_version", 2),
        ("snapshot_version", True),
        ("state_schema", "other_world_v1"),
        ("state_version", 2),
        ("state_version", True),
        ("semantic_key_version", "other_key_v1"),
    ):
        with pytest.raises(SnapshotValidationError):
            replace(snapshot, **{field: value})


def test_snapshot_json_rejects_duplicates_floats_and_unknown_fields() -> None:
    snapshot = _codec().capture(_world())
    encoded = snapshot.to_json()

    with pytest.raises(SnapshotValidationError, match="Duplicate JSON field"):
        PrivateWorldSnapshot.from_json('{"snapshot_version":1,"snapshot_version":1}')
    with pytest.raises(SnapshotValidationError, match="Floating-point"):
        PrivateWorldSnapshot.from_json('{"snapshot_version":1.0}')

    value = json.loads(encoded)
    value["unexpected"] = True
    with pytest.raises(SnapshotValidationError, match="fields"):
        PrivateWorldSnapshot.from_json(json.dumps(value))


def test_private_snapshot_is_type_and_api_distinct_from_public_observation() -> None:
    snapshot = _codec().capture(_world())

    assert PrivateWorldSnapshot is not PublicObservation
    assert not issubclass(PrivateWorldSnapshot, PublicObservation)
    assert not isinstance(snapshot, PublicObservation)
    assert not hasattr(snapshot, "phase")
    assert not hasattr(snapshot, "data")
    assert not hasattr(snapshot, "public_scope")
    with pytest.raises(SnapshotValidationError, match="private type"):
        _codec().restore(object())


def test_semantic_key_changes_for_private_continuation_state() -> None:
    base = _world()
    changed_gold = _codec().restore(_codec().capture(base))
    changed_gold.gold += 1
    changed_pending = _codec().restore(_codec().capture(base))
    changed_pending.pending_decision = PendingDecision("combat_action", 4, {})
    changed_rng = _codec().restore(_codec().capture(base))
    changed_rng.rng.randint(REWARD_OFFER_STREAM, 0, 10)

    assert len(
        {
            base.semantic_key(),
            changed_gold.semantic_key(),
            changed_pending.semantic_key(),
            changed_rng.semantic_key(),
        }
    ) == 4
