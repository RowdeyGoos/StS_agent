"""Tests for the opt-in exact card-record representation."""

from __future__ import annotations

from collections import Counter
from dataclasses import FrozenInstanceError
import hashlib
import json
import pickle

import pytest

from game.simulation.card_records import (
    APPLIED_STATUS_NAME_TO_ID,
    CARD_ID_CAPACITY,
    CARD_ID_TO_NAME,
    CARD_NAME_TO_ID,
    CARD_RECORD_FORMAT_VERSION,
    CARD_SEMANTIC_FEATURE_NAMES,
    DYNAMIC_DAMAGE_RULE_TO_ID,
    MAX_DISTINCT_RECORDS_PER_PILE,
    MAX_HAND_RECORDS,
    PILE_RECORD_ORDER,
    CardSemanticRecord,
    CardZoneRecords,
    PileCardRecord,
    card_record_schema_dict,
    card_record_schema_fingerprint,
    card_semantic_feature_table,
    extract_card_zone_records,
    get_action_card_id,
    get_card_id,
    get_card_semantic_record,
    validate_card_id_registry,
    validate_card_zone_records,
)
from game.simulation.card import create_ironclad_sequencing_deck
from game.simulation.core import CombatEnv
from game.simulation.encoding import PAD_CARD_NAME
from game.simulation.status import VULNERABLE


def _observation() -> dict[str, object]:
    return {
        "hand": ["Strike", "Bash", "Strike"],
        "draw_pile_size": 6,
        "discard_pile_size": 2,
        "exhaust_pile_size": 1,
        "card_counts": {
            "hand": {"Bash": 1, "Strike": 2},
            # Deliberately use non-ID insertion order. Extraction canonicalizes it.
            "draw_pile": {"Pommel Strike": 1, "Defend": 4, "Strike": 1},
            "discard_pile": {"Slimed": 1, "Bash": 1},
            "exhaust_pile": {"Slimed": 1},
        },
    }


def test_current_card_ids_are_stable_contiguous_and_below_capacity() -> None:
    expected_names = (
        PAD_CARD_NAME,
        "Strike",
        "Defend",
        "Bash",
        "Slimed",
        "Pommel Strike",
        "Shrug It Off",
        "Iron Wave",
        "Body Slam",
    )

    assert validate_card_id_registry(expected_prefix=expected_names) == expected_names
    assert dict(CARD_NAME_TO_ID) == {
        name: card_id for card_id, name in enumerate(expected_names)
    }
    assert dict(CARD_ID_TO_NAME) == {
        card_id: name for card_id, name in enumerate(expected_names)
    }
    assert max(CARD_ID_TO_NAME) < CARD_ID_CAPACITY == 256


def test_registry_validation_allows_only_append_only_contiguous_extensions() -> None:
    current_names = validate_card_id_registry()
    extended = dict(CARD_NAME_TO_ID)
    extended["Synthetic Appended Card"] = len(extended)

    assert validate_card_id_registry(
        extended,
        expected_prefix=current_names,
    )[-1] == "Synthetic Appended Card"

    renumbered = dict(extended)
    renumbered["Strike"] = 9
    with pytest.raises(ValueError, match="unique"):
        validate_card_id_registry(renumbered, expected_prefix=current_names)

    gapped = dict(CARD_NAME_TO_ID)
    gapped["Synthetic Gapped Card"] = 10
    with pytest.raises(ValueError, match="contiguous"):
        validate_card_id_registry(gapped)


def test_semantic_records_cover_static_dynamic_status_and_dead_cards() -> None:
    bash = get_card_semantic_record("Bash")
    shrug = get_card_semantic_record(get_card_id("Shrug It Off"))
    body_slam = get_card_semantic_record("Body Slam")
    slimed = get_card_semantic_record("Slimed")
    padding = get_card_semantic_record(0)

    assert (bash.damage_per_hit, bash.hit_count) == (8, 1)
    assert bash.applied_status_id == APPLIED_STATUS_NAME_TO_ID[VULNERABLE]
    assert bash.applied_status_stacks == 2
    assert (shrug.block_gain, shrug.draw_count, shrug.uses_target) == (8, 1, False)
    assert body_slam.dynamic_damage_rule_id == DYNAMIC_DAMAGE_RULE_TO_ID[
        "player_block"
    ]
    assert (body_slam.damage_per_hit, body_slam.hit_count) == (0, 1)
    assert slimed.exhausts is True
    assert (slimed.damage_per_hit, slimed.hit_count, slimed.uses_target) == (
        0,
        0,
        False,
    )
    assert padding.name == PAD_CARD_NAME
    assert padding.feature_values() == (0.0,) * len(CARD_SEMANTIC_FEATURE_NAMES)


def test_semantic_records_are_frozen_and_pickle_safe() -> None:
    record = get_card_semantic_record("Iron Wave")

    assert pickle.loads(pickle.dumps(record)) == record
    with pytest.raises(FrozenInstanceError):
        record.cost = 9  # type: ignore[misc]


def test_zone_extraction_preserves_hand_and_canonicalizes_exact_piles() -> None:
    records = extract_card_zone_records(_observation())

    assert records.hand_card_ids == (
        get_card_id("Strike"),
        get_card_id("Bash"),
        get_card_id("Strike"),
    )
    assert records.draw_pile == (
        PileCardRecord(get_card_id("Strike"), 1),
        PileCardRecord(get_card_id("Defend"), 4),
        PileCardRecord(get_card_id("Pommel Strike"), 1),
    )
    assert records.discard_pile == (
        PileCardRecord(get_card_id("Bash"), 1),
        PileCardRecord(get_card_id("Slimed"), 1),
    )
    assert records.exhaust_pile == (
        PileCardRecord(get_card_id("Slimed"), 1),
    )
    assert pickle.loads(pickle.dumps(records)) == records
    assert tuple(records.pile(name) for name in PILE_RECORD_ORDER) == (
        records.draw_pile,
        records.discard_pile,
        records.exhaust_pile,
    )


def test_zone_extraction_round_trips_an_environment_deck_composition() -> None:
    env = CombatEnv(
        deck_factory=create_ironclad_sequencing_deck,
        cards_per_turn=5,
    )
    records = extract_card_zone_records(env.reset(seed=7))
    observed_counts = Counter(records.hand_card_ids)
    for pile_name in PILE_RECORD_ORDER:
        observed_counts.update(
            {
                record.card_id: record.count
                for record in records.pile(pile_name)
            }
        )

    expected_counts = Counter(
        get_card_id(card.name) for card in create_ironclad_sequencing_deck()
    )
    assert observed_counts == expected_counts


def test_zone_extraction_accepts_zero_count_entries_without_emitting_records() -> None:
    observation = _observation()
    card_counts = observation["card_counts"]
    assert isinstance(card_counts, dict)
    draw_counts = card_counts["draw_pile"]
    assert isinstance(draw_counts, dict)
    draw_counts["Body Slam"] = 0

    records = extract_card_zone_records(observation)

    assert all(
        record.card_id != get_card_id("Body Slam") for record in records.draw_pile
    )


@pytest.mark.parametrize(
    ("mutator", "message"),
    (
        (
            lambda observation: observation.update(hand="Strike"),
            "hand.*list",
        ),
        (
            lambda observation: observation["hand"].append("Unknown Card"),
            "Unknown card name",
        ),
        (
            lambda observation: observation["card_counts"]["draw_pile"].update(
                {"Strike": -1}
            ),
            "non-negative integer",
        ),
        (
            lambda observation: observation["card_counts"]["draw_pile"].update(
                {"Strike": 1.5}
            ),
            "non-negative integer",
        ),
        (
            lambda observation: observation["card_counts"]["hand"].update(
                {"Strike": 1}
            ),
            "does not match",
        ),
        (
            lambda observation: observation.update(draw_pile_size=5),
            "exact card counts total",
        ),
    ),
)
def test_zone_extraction_rejects_inexact_or_malformed_observations(
    mutator: object,
    message: str,
) -> None:
    observation = _observation()
    mutator(observation)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        extract_card_zone_records(observation)


def test_zone_validation_rejects_duplicates_unknowns_counts_and_capacity() -> None:
    strike_id = get_card_id("Strike")
    duplicate_records = CardZoneRecords(
        hand_card_ids=(),
        draw_pile=(PileCardRecord(strike_id, 1), PileCardRecord(strike_id, 2)),
        discard_pile=(),
        exhaust_pile=(),
    )
    with pytest.raises(ValueError, match="unique, strictly ascending"):
        validate_card_zone_records(duplicate_records)

    invalid_count = CardZoneRecords(
        hand_card_ids=(),
        draw_pile=(PileCardRecord(strike_id, 0),),
        discard_pile=(),
        exhaust_pile=(),
    )
    with pytest.raises(ValueError, match="positive integer"):
        validate_card_zone_records(invalid_count)

    unknown_hand = CardZoneRecords(
        hand_card_ids=(99,),
        draw_pile=(),
        discard_pile=(),
        exhaust_pile=(),
    )
    with pytest.raises(ValueError, match="Unknown card ID"):
        validate_card_zone_records(unknown_hand)

    over_capacity = CardZoneRecords(
        hand_card_ids=(),
        draw_pile=tuple(
            PileCardRecord(strike_id, 1)
            for _ in range(MAX_DISTINCT_RECORDS_PER_PILE + 1)
        ),
        discard_pile=(),
        exhaust_pile=(),
    )
    with pytest.raises(ValueError, match="capacity"):
        validate_card_zone_records(over_capacity)

    too_many_hand_cards = CardZoneRecords(
        hand_card_ids=(strike_id,) * (MAX_HAND_RECORDS + 1),
        draw_pile=(),
        discard_pile=(),
        exhaust_pile=(),
    )
    with pytest.raises(ValueError, match="MAX_HAND_RECORDS"):
        validate_card_zone_records(too_many_hand_cards)


def test_action_card_lookup_uses_padding_for_end_turn_and_hand_id_for_play() -> None:
    observation = _observation()

    assert get_action_card_id(observation, ("end_turn",)) == 0
    assert get_action_card_id(observation, ("play", 1)) == get_card_id("Bash")
    assert get_action_card_id(observation, ("play", 2, 0)) == get_card_id("Strike")

    with pytest.raises(ValueError, match="out of range"):
        get_action_card_id(observation, ("play", 99))


def test_schema_dict_and_sha256_fingerprint_are_deterministic_and_complete() -> None:
    first = card_record_schema_dict()
    second = card_record_schema_dict()
    fingerprint = card_record_schema_fingerprint()
    canonical_json = json.dumps(
        first,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    assert first == second
    assert first["version"] == CARD_RECORD_FORMAT_VERSION == 1
    assert first["card_id_capacity"] == 256
    assert first["pile_record_order"] == list(PILE_RECORD_ORDER)
    assert [card["name"] for card in first["cards"]] == [
        CARD_ID_TO_NAME[card_id] for card_id in sorted(CARD_ID_TO_NAME)
    ]
    assert fingerprint == hashlib.sha256(canonical_json).hexdigest()
    assert len(fingerprint) == 64
    assert fingerprint == card_record_schema_fingerprint()


def test_semantic_feature_table_has_fixed_capacity_and_known_rows() -> None:
    table = card_semantic_feature_table()

    assert len(table) == CARD_ID_CAPACITY
    assert {len(row) for row in table} == {len(CARD_SEMANTIC_FEATURE_NAMES)}
    assert table[0] == (0.0,) * len(CARD_SEMANTIC_FEATURE_NAMES)
    assert table[get_card_id("Bash")] == get_card_semantic_record(
        "Bash"
    ).feature_values()
    assert table[9] == (0.0,) * len(CARD_SEMANTIC_FEATURE_NAMES)


def test_lookup_rejects_unknown_names_ids_and_types() -> None:
    with pytest.raises(ValueError, match="Unknown card name"):
        get_card_id("No Such Card")
    with pytest.raises(ValueError, match="Unknown card ID"):
        get_card_semantic_record(255)
    with pytest.raises(ValueError, match="booleans"):
        get_card_semantic_record(True)
    with pytest.raises(ValueError, match="name or integer ID"):
        get_card_semantic_record(1.5)  # type: ignore[arg-type]
