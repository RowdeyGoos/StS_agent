"""Tests for the closed reduced-run structural content fixture."""

from __future__ import annotations

import json
import pickle

import pytest

from game.content.reduced_v0 import (
    CARD_FACTORY_REFERENCES,
    CONTENT_EVIDENCE,
    CONTENT_FINGERPRINT,
    CONTENT_VERSION,
    MAP_TEMPLATES,
    REWARD_TABLES,
    REWARDABLE_CARD_DEFINITION_IDS,
    SAFE_EVENT_DEFINITIONS,
    SCENARIO_REFERENCES,
    SUPPORTED_CARD_DEFINITIONS,
    canonical_content_json,
    card_definition_from_dict,
    content_manifest,
    manifest_with_fingerprint,
    materialize_card_definition,
    resolve_scenario_reference,
    RewardTable,
)


def test_manifest_is_stable_json_and_has_structural_fixture_identity() -> None:
    manifest = content_manifest()
    assert manifest["content_version"] == CONTENT_VERSION == "reduced_content_v0"
    assert manifest["evidence"] == CONTENT_EVIDENCE == "structural_fixture"
    assert json.loads(canonical_content_json()) == manifest
    assert manifest_with_fingerprint()["content_fingerprint"] == CONTENT_FINGERPRINT
    assert len(CONTENT_FINGERPRINT) == 64
    assert CONTENT_FINGERPRINT == "fe771ea0f82c114d1d6a6389a44b169525c047914d955ce49d6db54e2472230f"


def test_every_serialized_card_definition_round_trips_and_materializes() -> None:
    for definition in SUPPORTED_CARD_DEFINITIONS:
        payload = json.loads(json.dumps(definition.to_dict()))
        decoded = card_definition_from_dict(payload)
        first = materialize_card_definition(decoded)
        second = materialize_card_definition(payload)
        assert decoded == definition
        assert first.name == definition.card_name
        assert type(first) is type(second)
        assert first is not second


@pytest.mark.parametrize(
    "payload",
    [
        {"definition_id": "strike", "card_name": "Strike", "factory_id": "missing"},
        {"definition_id": "strike", "card_name": "Changed", "factory_id": "strike"},
        {"definition_id": "strike", "card_name": "Strike", "factory_id": "strike", "extra": 1},
    ],
)
def test_unsupported_card_definitions_reject(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        materialize_card_definition(payload)


def test_factories_and_materializer_are_pickle_safe() -> None:
    restored_materializer = pickle.loads(pickle.dumps(materialize_card_definition))
    restored_factory = pickle.loads(pickle.dumps(CARD_FACTORY_REFERENCES["strike"]))
    assert restored_materializer(SUPPORTED_CARD_DEFINITIONS[0]).name == "Strike"
    assert restored_factory().name == "Strike"


def test_factory_lookup_is_immutable_and_registered_card_remains_stable() -> None:
    with pytest.raises(TypeError):
        CARD_FACTORY_REFERENCES["strike"] = CARD_FACTORY_REFERENCES["defend"]
    assert materialize_card_definition(SUPPORTED_CARD_DEFINITIONS[0]).name == "Strike"


def test_reward_tables_reject_transient_combat_only_cards() -> None:
    assert "slimed" not in REWARDABLE_CARD_DEFINITION_IDS
    with pytest.raises(ValueError, match="persistent"):
        RewardTable("invalid_transient_reward", 10, ("slimed",))


def test_references_resolve_and_content_is_closed() -> None:
    assert len(SCENARIO_REFERENCES) >= 2
    assert [resolve_scenario_reference(item).scenario_id for item in SCENARIO_REFERENCES] == list(SCENARIO_REFERENCES)
    assert all(table.card_definition_ids for table in REWARD_TABLES)
    assert all(template.nodes for template in MAP_TEMPLATES)
    assert SAFE_EVENT_DEFINITIONS
    assert content_manifest()["unsupported_content"] == [
        "shops", "potions", "upgrades", "procedural_maps", "broad_events"
    ]
