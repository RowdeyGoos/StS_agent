#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from decision_providers import (
    get_decision_provider,
    get_map_decision_provider,
    map_provider_names,
)
from tool_common import EXIT_MISMATCH, fail, main


def _candidate(
    index: int,
    kind: str,
    col: int,
    row: int = 4,
) -> dict[str, object]:
    return {
        "candidate_index": index,
        "col": col,
        "row": row,
        "kind": kind,
    }


def _action(index: int) -> dict[str, object]:
    return {
        "action_id": f"select:{index}",
        "kind": "select_map_node",
        "candidate_index": index,
    }


def _require_selection(
    selected: dict[str, object],
    action: dict[str, object],
    candidate: dict[str, object],
    basis: str,
) -> None:
    expected = {
        "action_id": action["action_id"],
        "kind": action["kind"],
        "candidate_index": action["candidate_index"],
        "col": candidate["col"],
        "row": candidate["row"],
        "node_kind": candidate["kind"],
        "basis": basis,
    }
    if selected != expected:
        fail(EXIT_MISMATCH, "map_provider_fixture_selection")


def _priority() -> None:
    candidates = [
        _candidate(0, "unknown", 1),
        _candidate(1, "monster", 2),
        _candidate(2, "ancient", 3),
        _candidate(3, "rest_site", 4),
    ]
    actions = [_action(0), _action(1), _action(2), _action(3)]
    _require_selection(
        get_map_decision_provider("first").choose(candidates, actions),
        actions[0],
        candidates[0],
        "first_reachable",
    )
    _require_selection(
        get_map_decision_provider("combat").choose(candidates, actions),
        actions[1],
        candidates[1],
        "combat_continuation",
    )
    _require_selection(
        get_map_decision_provider("coverage").choose(candidates, actions),
        actions[3],
        candidates[3],
        "room_coverage",
    )

    without_rest = candidates[:3]
    _require_selection(
        get_map_decision_provider("coverage").choose(without_rest, actions[:3]),
        actions[2],
        candidates[2],
        "room_coverage",
    )


def _fallback() -> None:
    candidates = [
        _candidate(0, "shop", 5),
        _candidate(1, "treasure", 3),
    ]
    actions = [_action(0), _action(1)]
    _require_selection(
        get_map_decision_provider("combat").choose(candidates, actions),
        actions[1],
        candidates[1],
        "combat_continuation",
    )
    _require_selection(
        get_map_decision_provider("coverage").choose(candidates, actions),
        actions[1],
        candidates[1],
        "room_coverage",
    )


def _advertised_legal_alignment() -> None:
    candidates = [
        _candidate(0, "rest_site", 1),
        _candidate(1, "monster", 2),
        _candidate(2, "unknown", 3),
    ]
    advertised_actions = [_action(1), _action(2)]
    selected = get_map_decision_provider("coverage").choose(
        candidates,
        advertised_actions,
    )
    _require_selection(
        selected,
        advertised_actions[0],
        candidates[1],
        "room_coverage",
    )
    if not any(
        selected["action_id"] == action["action_id"]
        and selected["kind"] == action["kind"]
        and selected["candidate_index"] == action["candidate_index"]
        for action in advertised_actions
    ):
        fail(EXIT_MISMATCH, "map_provider_fixture_unadvertised_action")


def _deterministic_tie_breaking() -> None:
    candidates = [
        _candidate(0, "monster", 1, row=5),
        _candidate(1, "monster", 9, row=4),
        _candidate(2, "monster", 2, row=4),
    ]
    actions = [_action(2), _action(1), _action(0)]
    _require_selection(
        get_map_decision_provider("coverage").choose(candidates, actions),
        actions[0],
        candidates[2],
        "room_coverage",
    )

    tied_candidates = [
        _candidate(0, "monster", 2),
        _candidate(1, "monster", 2),
    ]
    tied_actions = [_action(1), _action(0)]
    _require_selection(
        get_map_decision_provider("coverage").choose(tied_candidates, tied_actions),
        tied_actions[1],
        tied_candidates[0],
        "room_coverage",
    )


def _combat_followup_safety() -> None:
    enemies = [{"hp": 20, "intents": ["attack"]}]
    hand = [
        {"id": "SURVIVOR", "type": "skill"},
        {"id": "PREPARED", "type": "skill"},
        {"id": "STRIKE_SILENT", "type": "attack"},
    ]
    survivor = {
        "action_id": "play:0",
        "kind": "play_card",
        "hand_index": 0,
        "target_index": None,
    }
    strike = {
        "action_id": "play:2:0",
        "kind": "play_card",
        "hand_index": 2,
        "target_index": 0,
    }
    prepared = {
        "action_id": "play:1",
        "kind": "play_card",
        "hand_index": 1,
        "target_index": None,
    }
    end_turn = {
        "action_id": "end_turn",
        "kind": "end_turn",
        "hand_index": None,
        "target_index": None,
    }
    provider = get_decision_provider("heuristic")
    selected = provider.choose(
        enemies,
        hand,
        [survivor, prepared, strike, end_turn],
    )
    if selected != {
        **strike,
        "card_id": "STRIKE_SILENT",
        "basis": "incoming_attack",
    }:
        fail(EXIT_MISMATCH, "combat_provider_fixture_followup_avoidance")

    selected = provider.choose(
        enemies,
        hand[:2],
        [survivor, prepared, end_turn],
    )
    if selected != {
        **end_turn,
        "card_id": None,
        "basis": "no_safe_card",
    }:
        fail(EXIT_MISMATCH, "combat_provider_fixture_followup_end_turn")


def operation() -> dict[str, object]:
    checks: list[str] = []
    if map_provider_names() != frozenset(("first", "combat", "coverage")):
        fail(EXIT_MISMATCH, "map_provider_fixture_registry")
    checks.append("provider_registry")
    _priority()
    checks.append("priority")
    _fallback()
    checks.append("fallback")
    _advertised_legal_alignment()
    checks.append("advertised_legal_alignment")
    _deterministic_tie_breaking()
    checks.append("deterministic_tie_breaking")
    _combat_followup_safety()
    checks.append("combat_followup_safety")
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "decision_providers_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
