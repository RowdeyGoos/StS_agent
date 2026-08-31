"""Structural-fixture coverage for the project-authored RNG service."""

from __future__ import annotations

import json
from copy import deepcopy
from random import Random

import pytest

from game.engine.random_service import (
    RANDOM_SERVICE_SCHEMA,
    RANDOM_SERVICE_SNAPSHOT_VERSION,
    GameRandomService,
)


def _exercise(service: GameRandomService) -> tuple[int, str, list[int]]:
    values = [0, 1, 2, 3, 4]
    result = (
        service.randint("combat_launch", 10, 99),
        service.choice("reward_offer", ("strike", "defend", "bash")),
        values,
    )
    service.shuffle("event_effect", values)
    return result


def test_same_seed_and_named_requests_produce_the_same_results() -> None:
    first = GameRandomService(seed=291)
    second = GameRandomService(seed=291)

    assert _exercise(first) == _exercise(second)
    assert first.stream_names == ("combat_launch", "event_effect", "reward_offer")
    assert first.request_count("combat_launch") == 1
    assert first.request_count("reward_offer") == 1
    assert first.request_count("event_effect") == 1
    assert first.snapshot() == second.snapshot()


def test_json_snapshot_restore_continues_every_stream_exactly() -> None:
    original = GameRandomService(seed=882)
    original.randint("combat_launch", 0, 1000)
    original.choice("reward_offer", ("a", "b", "c"))
    snapshot = json.loads(json.dumps(original.snapshot()))

    restored = GameRandomService(seed=0)
    restored.restore(snapshot)

    assert restored.snapshot() == snapshot
    assert restored.randint("combat_launch", 0, 1000) == original.randint(
        "combat_launch", 0, 1000
    )
    assert restored.choice("reward_offer", ("a", "b", "c")) == original.choice(
        "reward_offer", ("a", "b", "c")
    )
    original_values = [1, 2, 3, 4]
    restored_values = [1, 2, 3, 4]
    original.shuffle("event_effect", original_values)
    restored.shuffle("event_effect", restored_values)
    assert restored_values == original_values
    assert restored.snapshot() == original.snapshot()


def test_named_streams_are_isolated_from_unrelated_game_requests() -> None:
    baseline = GameRandomService(seed=41)
    with_unrelated_requests = GameRandomService(seed=41)

    expected = [baseline.randint("combat_launch", 0, 1_000_000) for _ in range(4)]
    for _ in range(50):
        with_unrelated_requests.choice("reward_offer", ("a", "b", "c"))
        values = [0, 1, 2, 3]
        with_unrelated_requests.shuffle("event_effect", values)
    actual = [
        with_unrelated_requests.randint("combat_launch", 0, 1_000_000)
        for _ in range(4)
    ]

    assert actual == expected
    assert baseline.request_count("reward_offer") == 0
    assert with_unrelated_requests.request_count("reward_offer") == 50
    assert with_unrelated_requests.request_count("event_effect") == 50


def test_unrelated_policy_rng_cannot_change_game_stream_results() -> None:
    game = GameRandomService(seed=707)
    expected = GameRandomService(seed=707)
    policy_rng = Random(12345)

    game_results = []
    for _ in range(12):
        policy_rng.randrange(10_000)
        policy_rng.choice(("left", "right"))
        game_results.append(game.randint("combat_launch", 0, 10_000))

    assert game_results == [
        expected.randint("combat_launch", 0, 10_000) for _ in range(12)
    ]
    assert game.request_count("combat_launch") == 12


@pytest.mark.parametrize(
    "mutate",
    [
        lambda snapshot: snapshot.__setitem__("schema", "other_rng_v1"),
        lambda snapshot: snapshot.__setitem__("snapshot_version", 2),
        lambda snapshot: snapshot.__setitem__("snapshot_version", True),
        lambda snapshot: snapshot.__setitem__("unexpected", True),
        lambda snapshot: snapshot.__setitem__("streams", []),
        lambda snapshot: snapshot["streams"].__setitem__(
            "combat_launch", {"request_count": -1, "state": {}}
        ),
        lambda snapshot: snapshot["streams"]["combat_launch"].__setitem__(
            "request_count", True
        ),
        lambda snapshot: snapshot["streams"]["combat_launch"]["state"].__setitem__(
            "version", 999
        ),
        lambda snapshot: snapshot["streams"]["combat_launch"]["state"].__setitem__(
            "version", 3.0
        ),
        lambda snapshot: snapshot["streams"]["combat_launch"]["state"].__setitem__(
            "internal_state", [0] * 10
        ),
        lambda snapshot: snapshot["streams"]["combat_launch"]["state"].__setitem__(
            "gauss_next", 1.5
        ),
    ],
)
def test_malformed_or_version_mismatched_snapshot_rejects_atomically(mutate) -> None:
    service = GameRandomService(seed=6)
    service.randint("combat_launch", 0, 9)
    valid_snapshot = service.snapshot()
    malformed_snapshot = deepcopy(valid_snapshot)
    mutate(malformed_snapshot)

    with pytest.raises(ValueError):
        service.restore(malformed_snapshot)

    assert service.snapshot() == valid_snapshot


def test_snapshot_schema_is_explicit_and_json_safe() -> None:
    service = GameRandomService(seed=-4)
    service.randint("combat_launch", -5, 5)

    snapshot = service.snapshot()

    assert snapshot["schema"] == RANDOM_SERVICE_SCHEMA
    assert snapshot["snapshot_version"] == RANDOM_SERVICE_SNAPSHOT_VERSION
    assert snapshot["streams"]["combat_launch"]["state"]["gauss_next"] is None
    assert isinstance(snapshot["streams"]["combat_launch"]["state"]["internal_state"], list)
    assert json.loads(json.dumps(snapshot)) == snapshot


def test_invalid_game_requests_reject_without_creating_streams() -> None:
    service = GameRandomService(seed=1)

    with pytest.raises(ValueError):
        service.randint("combat_launch", 2, 1)
    with pytest.raises(ValueError):
        service.choice("reward_offer", ())
    with pytest.raises(ValueError):
        service.randint("", 0, 1)
    with pytest.raises(TypeError):
        service.shuffle("event_effect", (1, 2, 3))

    assert service.stream_names == ()
