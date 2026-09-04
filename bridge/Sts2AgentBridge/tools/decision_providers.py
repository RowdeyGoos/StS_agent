#!/usr/bin/env python3
from __future__ import annotations

from typing import Protocol


_UNSUPPORTED_FOLLOWUP_CARD_IDS = frozenset(("prepared", "survivor"))


class DecisionProvider(Protocol):
    def choose(
        self,
        enemies: list[dict[str, object]],
        hand: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        ...


def _selection(
    selected: dict[str, object],
    hand: list[dict[str, object]],
    basis: str,
) -> dict[str, object]:
    hand_index = selected["hand_index"]
    return {
        "action_id": selected["action_id"],
        "kind": selected["kind"],
        "hand_index": hand_index,
        "target_index": selected["target_index"],
        "card_id": None if hand_index is None else hand[int(hand_index)]["id"],
        "basis": basis,
    }


class HeuristicDecisionProvider:
    def choose(
        self,
        enemies: list[dict[str, object]],
        hand: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        incoming_attack = any(
            "attack" in str(intent).lower()
            for enemy in enemies
            for intent in enemy["intents"]
        )
        candidates = [
            action
            for action in actions
            if action["kind"] == "play_card"
            and str(hand[int(action["hand_index"])]["id"]).lower()
            not in _UNSUPPORTED_FOLLOWUP_CARD_IDS
        ]
        if not candidates:
            selected = next(action for action in actions if action["kind"] == "end_turn")
            return _selection(selected, hand, "no_safe_card")

        def rank(action: dict[str, object]) -> tuple[int, int, int, int]:
            hand_index = int(action["hand_index"])
            card = hand[hand_index]
            card_id = str(card["id"]).lower()
            card_type = str(card["type"]).lower()
            if incoming_attack:
                category = 0 if "defend" in card_id else 1 if card_type == "skill" else 2 if card_type == "attack" else 3
            else:
                category = 0 if "bash" in card_id else 1 if card_type == "attack" else 2 if card_type == "skill" else 3
            target_index = action["target_index"]
            target_hp = enemies[int(target_index)]["hp"] if target_index is not None else 1_000_001
            return category, int(target_hp), hand_index, -1 if target_index is None else int(target_index)

        selected = min(candidates, key=rank)
        return _selection(
            selected,
            hand,
            "incoming_attack" if incoming_attack else "no_visible_attack",
        )


class FirstLegalDecisionProvider:
    def choose(
        self,
        enemies: list[dict[str, object]],
        hand: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        del enemies
        selected = actions[0]
        return _selection(selected, hand, "first_legal")


_PROVIDERS: dict[str, DecisionProvider] = {
    "heuristic": HeuristicDecisionProvider(),
    "first-legal": FirstLegalDecisionProvider(),
}


def get_decision_provider(name: str) -> DecisionProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as error:
        raise ValueError("unknown decision provider") from error


def provider_names() -> frozenset[str]:
    return frozenset(_PROVIDERS)


class MapDecisionProvider(Protocol):
    def choose(
        self,
        candidates: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        ...


class FirstMapDecisionProvider:
    def choose(
        self,
        candidates: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        return _map_selection(actions[0], candidates, "first_reachable")


def _map_selection(
    selected: dict[str, object],
    candidates: list[dict[str, object]],
    basis: str,
) -> dict[str, object]:
    candidate = candidates[int(selected["candidate_index"])]
    return {
        "action_id": selected["action_id"],
        "kind": selected["kind"],
        "candidate_index": selected["candidate_index"],
        "col": candidate["col"],
        "row": candidate["row"],
        "node_kind": candidate["kind"],
        "basis": basis,
    }


def _rank_map_action(
    action: dict[str, object],
    candidates: list[dict[str, object]],
    priorities: dict[str, int],
) -> tuple[int, int, int, int, str]:
    candidate_index = int(action["candidate_index"])
    candidate = candidates[candidate_index]
    return (
        priorities.get(str(candidate["kind"]), len(priorities)),
        int(candidate["row"]),
        int(candidate["col"]),
        candidate_index,
        str(action["action_id"]),
    )


class CombatMapDecisionProvider:
    def choose(
        self,
        candidates: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        selected = min(
            actions,
            key=lambda action: _rank_map_action(action, candidates, {"monster": 0}),
        )
        return _map_selection(selected, candidates, "combat_continuation")


class CoverageMapDecisionProvider:
    def choose(
        self,
        candidates: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        priorities = {
            "rest_site": 0,
            "ancient": 1,
            "monster": 2,
        }
        selected = min(
            actions,
            key=lambda action: _rank_map_action(action, candidates, priorities),
        )
        return _map_selection(selected, candidates, "room_coverage")


class EliteMapDecisionProvider:
    def choose(
        self,
        candidates: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        priorities = {
            "elite": 0,
            "rest_site": 1,
            "monster": 2,
            "ancient": 3,
        }
        selected = min(
            actions,
            key=lambda action: _rank_map_action(action, candidates, priorities),
        )
        return _map_selection(selected, candidates, "elite_continuation")


_MAP_PROVIDERS: dict[str, MapDecisionProvider] = {
    "first": FirstMapDecisionProvider(),
    "combat": CombatMapDecisionProvider(),
    "coverage": CoverageMapDecisionProvider(),
    "elite": EliteMapDecisionProvider(),
}


def get_map_decision_provider(name: str) -> MapDecisionProvider:
    try:
        return _MAP_PROVIDERS[name]
    except KeyError as error:
        raise ValueError("unknown map decision provider") from error


def map_provider_names() -> frozenset[str]:
    return frozenset(_MAP_PROVIDERS)
