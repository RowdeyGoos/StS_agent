#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import time
from pathlib import Path
from typing import Any, Callable

import probe_live as probe
from reward_action_diagnostics import RewardActionDiagnostics
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_APPLY_DEADLINE_SECONDS = 45.0
_POLL_SECONDS = 0.1
_MAXIMUM_ACCEPTED_ACTIONS = 17
_PROVIDERS = frozenset(("first-card", "skip-card", "skip"))
_REWARD_WAITING = (
    b'{"schema_version":1,"status":"waiting","decision_kind":"reward",'
    b'"actionable":false,"decision_id":null,"screen_kind":"unknown",'
    b'"player":null,"rewards":[],"legal_actions":[]}'
)
_REWARD_UNSUPPORTED = _REWARD_WAITING.replace(b'"waiting"', b'"unsupported"')


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 6:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(("--user-profile", "--effective-uid", "--decision-provider"))
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    if parsed["--decision-provider"] not in _PROVIDERS:
        fail(EXIT_INVALID_INVOCATION, "invalid_decision_provider")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        parsed["--decision-provider"],
    )


def _read_body(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytes:
    response = probe._exchange(
        label,
        route,
        credential,
        connector,
        deadline,
        decision_id,
        action_id,
    )
    body: memoryview | None = None
    try:
        body = probe._canonical_body(response, label)
        return bytes(body)
    finally:
        if body is not None:
            body.release()
        probe._zero(response)


def _read_reward_action_body(
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str,
    action_id: str,
    action_category: str,
    diagnostics: RewardActionDiagnostics | None,
) -> bytes:
    """Read one action response, optionally classifying it before zeroization."""
    if diagnostics is None:
        return _read_body(
            "reward_action", probe._REWARD_ACTION_ROUTE, credential, connector,
            deadline, decision_id, action_id,
        )
    diagnostics.attempted_exchange(action_category)
    response: bytearray | None = None
    body: memoryview | None = None
    try:
        try:
            response = probe._exchange(
                "reward_action", probe._REWARD_ACTION_ROUTE, credential, connector,
                deadline, decision_id, action_id,
            )
        except ToolFailure as failure:
            diagnostics.transport_failure(failure.error_code)
            raise
        classification = diagnostics.inspect_http_response(response)
        if classification is not None:
            diagnostics.http_failure(classification)
            fail(EXIT_MISMATCH, "reward_action_response_mismatch")
        try:
            body = probe._canonical_body(response, "reward_action")
            return bytes(body)
        except ToolFailure as failure:
            if failure.error_code == "reward_action_response_too_large":
                diagnostics.http_failure("http_response_oversize")
            else:
                diagnostics.http_failure()
            raise
    finally:
        if body is not None:
            body.release()
        if response is not None:
            probe._zero(response)


def _decode_exact(body: bytes, keys: tuple[str, ...]) -> dict[str, object]:
    try:
        root = json.loads(
            body.decode("ascii"),
            object_pairs_hook=probe._unique_object,
            parse_constant=probe._reject_json_constant,
        )
        return probe._validate_exact_keys(root, keys)
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "reward_response_mismatch")


def _validate_player(value: object) -> dict[str, int]:
    player = probe._validate_exact_keys(value, ("hp", "max_hp", "gold", "deck_count"))
    if any(not probe._is_bounded_nonnegative_integer(player[name]) for name in player):
        raise ValueError("player values")
    if player["hp"] < 1 or player["max_hp"] < 1 or player["hp"] > player["max_hp"]:
        raise ValueError("player health")
    if player["deck_count"] < 1:
        raise ValueError("deck count")
    return {name: int(value) for name, value in player.items()}


def _validate_reward(raw_reward: object, expected_slot: int, schema: int = 1) -> dict[str, object]:
    reward = probe._validate_exact_keys(
        raw_reward,
        (
            "reward_slot",
            "reward_index",
            "kind",
            "successfully_selected",
            "gold_amount",
            "cards",
            "card_selection_can_skip",
        ) + (("item_key",) if schema >= 3 else ()) + (("potion_capacity_gain",) if schema >= 5 else ()) + (("heal_amount",) if schema == 6 else ()),
    )
    if reward["reward_slot"] != expected_slot:
        raise ValueError("reward slot")
    if not probe._is_bounded_nonnegative_integer(reward["reward_index"]):
        raise ValueError("reward index")
    if type(reward["successfully_selected"]) is not bool:
        raise ValueError("reward selection")
    if type(reward["card_selection_can_skip"]) is not bool:
        raise ValueError("card skip")
    cards = reward["cards"]
    if not isinstance(cards, list) or len(cards) > 5 or any(
        not probe._is_public_string(card) for card in cards
    ):
        raise ValueError("reward cards")
    if reward["kind"] == "gold":
        if (
            not probe._is_bounded_nonnegative_integer(reward["gold_amount"])
            or cards != []
            or reward["card_selection_can_skip"] is not False
        ):
            raise ValueError("gold reward")
    elif reward["kind"] == "card":
        if reward["gold_amount"] is not None or not cards:
            raise ValueError("card reward")
    elif reward["kind"] == "special_card":
        if reward["gold_amount"] is not None or len(cards) != 1 or reward["card_selection_can_skip"] is not False:
            raise ValueError("special card reward")
    elif reward["kind"] in ("potion", "relic"):
        if (schema < 3 or reward["gold_amount"] is not None or cards or reward["card_selection_can_skip"] is not False or
                type(reward["item_key"]) is not str or not 1 <= len(reward["item_key"]) <= 128 or
                any(not (c.isascii() and (c.isalnum() or c == "_")) for c in reward["item_key"])):
            raise ValueError("item reward")
    elif reward["kind"] == "unsupported":
        if (
            reward["gold_amount"] is not None
            or cards != []
            or reward["card_selection_can_skip"] is not False
        ):
            raise ValueError("unsupported reward")
    else:
        raise ValueError("reward kind")
    if schema >= 3 and reward["kind"] not in ("potion", "relic") and reward["item_key"] is not None:
        raise ValueError("unexpected item key")
    if schema >= 5:
        gain=reward["potion_capacity_gain"]
        if type(gain) is not int or gain not in (0,2) or gain and (reward["kind"]!="relic" or reward["item_key"]!="POTION_BELT"):
            raise ValueError("capacity gain")
    return reward


def _validate_action(raw_action: object, screen_kind: str, schema: int = 1) -> dict[str, object]:
    action = probe._validate_exact_keys(
        raw_action,
        ("action_id", "kind", "reward_slot", "card_slot") + (("potion_slot",) if schema >= 4 else ()),
    )
    if schema >= 4:
        if action["kind"] == "discard_potion":
            slot=action["potion_slot"]
            if screen_kind != "rewards" or type(slot) is not int or not 0<=slot<=7 or action["action_id"] != "discard:"+str(slot) or action["reward_slot"] is not None or action["card_slot"] is not None:
                raise ValueError("potion discard")
            return action
        if action["potion_slot"] is not None:raise ValueError("unexpected potion slot")
        action=dict(action);action.pop("potion_slot")
    action_id = action["action_id"]
    if not isinstance(action_id, str):
        raise ValueError("action id")
    if screen_kind == "rewards":
        if action["kind"] == "claim_gold":
            prefix = "claim:"
        elif action["kind"] == "collect_item":
            prefix = "collect:"
        elif action["kind"] == "claim_special_card":
            prefix = "take:"
        elif action["kind"] == "open_card":
            prefix = "open:"
        elif action["kind"] == "proceed":
            if action != {
                "action_id": "proceed",
                "kind": "proceed",
                "reward_slot": None,
                "card_slot": None,
            }:
                raise ValueError("proceed")
            return action
        else:
            raise ValueError("parent action kind")
        reward_slot = action["reward_slot"]
        if (
            type(reward_slot) is not int
            or reward_slot < 0
            or reward_slot > 7
            or action["card_slot"] is not None
            or action_id != prefix + str(reward_slot)
        ):
            raise ValueError("parent action")
        return action

    if action["kind"] == "choose_card":
        card_slot = action["card_slot"]
        if (
            type(card_slot) is not int
            or card_slot < 0
            or card_slot > 4
            or action["reward_slot"] is not None
            or action_id != "choose:" + str(card_slot)
        ):
            raise ValueError("card choice")
        return action
    if action != {
        "action_id": "skip_card",
        "kind": "skip_card",
        "reward_slot": None,
        "card_slot": None,
    }:
        raise ValueError("child action")
    return action


def _validate_ready(body: bytes) -> dict[str, object]:
    try:
        schema = json.loads(body)["schema_version"]
        root = _decode_exact(
            body,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "decision_revision",
                "screen_kind",
                "player",
                "rewards",
                "legal_actions",
            ) + (("potion_slots",) if schema >= 4 else ()),
        )
        decision_id = root["decision_id"]
        revision = root["decision_revision"]
        screen_kind = root["screen_kind"]
        if (
            type(root["schema_version"]) is not int or root["schema_version"] not in (1, 2, 3, 4, 5, 6)
            or root["status"] != "ready"
            or root["decision_kind"] != "reward"
            or root["actionable"] is not True
            or screen_kind not in ("rewards", "card_reward")
            or not isinstance(decision_id, str)
            or len(decision_id) != 64
            or any(ord(value) not in probe._LOWER_HEX for value in decision_id)
            or not probe._is_bounded_nonnegative_integer(revision)
        ):
            raise ValueError("reward header")
        player = _validate_player(root["player"])

        raw_rewards = root["rewards"]
        if not isinstance(raw_rewards, list) or len(raw_rewards) > 8:
            raise ValueError("reward count")
        if screen_kind == "card_reward" and len(raw_rewards) != 1:
            raise ValueError("child reward count")
        rewards: list[dict[str, object]] = []
        previous_index = -1
        for slot, raw_reward in enumerate(raw_rewards):
            reward = _validate_reward(raw_reward, slot, root["schema_version"])
            if int(reward["reward_index"]) <= previous_index:
                raise ValueError("reward index order")
            if schema == 6:
                heal=reward["heal_amount"]
                expected=player["max_hp"]//10 if reward["kind"]=="relic" and reward["item_key"]=="FAKE_LEES_WAFFLE" else 0
                if type(heal) is not int or heal!=expected:raise ValueError("healing effect")
            previous_index = int(reward["reward_index"])
            rewards.append(reward)

        special = any(r["kind"] == "special_card" for r in rewards)
        if root["schema_version"] < 3 and root["schema_version"] != (2 if special else 1):
            raise ValueError("reward schema")

        raw_actions = root["legal_actions"]
        if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= (17 if schema >= 4 else 9):
            raise ValueError("legal action count")
        actions = [_validate_action(action, str(screen_kind), schema) for action in raw_actions]
        action_ids = [str(action["action_id"]) for action in actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("duplicate action")

        potions=root.get("potion_slots")
        if schema >= 4:
            if type(potions) is not list or len(potions)>8 or any(p is not None and (type(p) is not str or not 1<=len(p)<=128 or any(not(c.isascii() and (c.isalnum() or c=='_')) for c in p)) for p in potions):
                raise ValueError("potion inventory")
        if screen_kind == "rewards":
            if action_ids[-1] != "proceed" or action_ids.count("proceed") != 1:
                raise ValueError("parent proceed")
            for action in actions[:-1]:
                if action['kind']=='discard_potion':
                    if schema<4 or not potions or any(p is None for p in potions) or action['potion_slot']>=len(potions) or not any(r['kind']=='potion' and not r['successfully_selected'] for r in rewards):raise ValueError('discard target')
                    continue
                reward = rewards[int(action["reward_slot"])]
                if action["kind"]=="collect_item" and reward.get("potion_capacity_gain",0)>0 and (potions is None or len(potions)+reward["potion_capacity_gain"]>8):
                    raise ValueError("capacity bound")
                expected_kinds = {"claim_gold": ("gold",), "claim_special_card": ("special_card",), "open_card": ("card",), "collect_item": ("potion", "relic")}[action["kind"]]
                if reward["kind"] not in expected_kinds or reward["successfully_selected"] is True:
                    raise ValueError("parent target")
        else:
            reward = rewards[0]
            if reward["kind"] != "card":
                raise ValueError("child reward")
            cards = reward["cards"]
            for action in actions:
                if action["kind"] == "choose_card" and int(action["card_slot"]) >= len(cards):
                    raise ValueError("card target")
                if action["kind"] == "skip_card" and reward["card_selection_can_skip"] is not True:
                    raise ValueError("illegal card skip")
    except (ValueError, TypeError, KeyError, IndexError):
        fail(EXIT_MISMATCH, "reward_response_mismatch")

    return {
        "decision_id": decision_id,
        "decision_revision": int(revision),
        "screen_kind": screen_kind,
        "player": player,
        "rewards": rewards,
        "legal_actions": actions,
        **({"potion_slots": potions} if schema >= 4 else {}),
        **({"capacity_rewards": True} if schema >= 5 else {}),
        **({"healing_rewards": True} if schema == 6 else {}),
    }


def _validate_complete(body: bytes) -> dict[str, object]:
    try:
        root = _decode_exact(
            body,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "screen_kind",
                "player",
                "rewards",
                "legal_actions",
            ),
        )
        if (
            root["schema_version"] != 1
            or root["status"] != "complete"
            or root["decision_kind"] != "reward"
            or root["actionable"] is not False
            or root["decision_id"] is not None
            or root["screen_kind"] != "map"
            or root["rewards"] != []
            or root["legal_actions"] != []
        ):
            raise ValueError("reward completion")
        player = _validate_player(root["player"])
    except (ValueError, TypeError, KeyError, IndexError):
        fail(EXIT_MISMATCH, "reward_complete_response_mismatch")
    return {"screen_kind": "map", "player": player}


def _validate_action_response(body: bytes, decision_id: str, action_id: str) -> None:
    expected = (
        b'{"schema_version":1,"status":"accepted","mutation_state":"applied",'
        b'"decision_id":"'
        + decision_id.encode("ascii")
        + b'","action_id":"'
        + action_id.encode("ascii")
        + b'","reason":"accepted"}'
    )
    if body != expected:
        fail(EXIT_MISMATCH, "reward_action_response_mismatch")


def _capacity_action(state):
    """A legal, declared pickup can make space before a blocked potion."""
    actions=state["legal_actions"]
    ids={a["action_id"] for a in actions}
    blocked=any(r["kind"]=="potion" and not r["successfully_selected"] and "collect:"+str(i) not in ids
                for i,r in enumerate(state["rewards"]))
    if blocked and state.get("capacity_rewards") and "potion_slots" in state:
        for action in actions:
            if action["kind"]=="collect_item":
                reward=state["rewards"][action["reward_slot"]]
                gain=reward.get("potion_capacity_gain",0)
                if gain>0 and len(state["potion_slots"])+gain<=8:return action
    return None


def _choose_action(state: dict[str, object], provider: str, potion_policy: str = "stop-on-full") -> dict[str, object]:
    if potion_policy not in ("stop-on-full", "skip-full", "skip-all", "replace-first"):
        fail(EXIT_MISMATCH, "potion_policy")
    actions = list(state["legal_actions"])
    if state["screen_kind"] == "rewards":
        capacity_action = _capacity_action(state)
        action_ids = {action["action_id"] for action in actions}
        for slot, reward in enumerate(state["rewards"]):
            if reward["kind"] in ("potion", "relic") and not reward["successfully_selected"] and "collect:" + str(slot) not in action_ids and not (reward["kind"] == "potion" and (potion_policy != "stop-on-full" or capacity_action is not None)):
                fail(EXIT_MISMATCH, "potion_inventory_full" if reward["kind"] == "potion" else "unresolved_reward")
        for kind in ("claim_gold", "collect_item", "claim_special_card", "open_card", "discard_potion", "proceed"):
            if kind=="collect_item" and capacity_action is not None:return capacity_action
            for action in actions:
                if action["kind"] == kind:
                    if kind == "discard_potion" and potion_policy != "replace-first":continue
                    if kind == "proceed" and potion_policy == "replace-first" and any(r["kind"]=="potion" and not r["successfully_selected"] for r in state["rewards"]):fail(EXIT_MISMATCH,"potion_replacement_unavailable")
                    if kind == "collect_item" and potion_policy == "skip-all" and state["rewards"][int(action["reward_slot"])]["kind"] == "potion":
                        continue
                    return action
    else:
        desired = "choose_card" if provider == "first-card" else "skip_card"
        for action in actions:
            if action["kind"] == desired:
                return action
        if desired == "skip_card":
            fail(EXIT_MISMATCH, "card_reward_not_skippable")
    fail(EXIT_MISMATCH, "reward_provider_no_action")


def _poll_next(
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    prior_decision_id: str,
) -> dict[str, object]:
    while time.monotonic() < deadline:
        observed = _read_body(
            "reward",
            probe._REWARD_ROUTE[0][1],
            credential,
            connector,
            deadline,
        )
        if observed == _REWARD_WAITING:
            time.sleep(_POLL_SECONDS)
            continue
        if observed == _REWARD_UNSUPPORTED:
            fail(EXIT_MISMATCH, "post_reward_state_unsupported")
        try:
            decoded = json.loads(observed.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            fail(EXIT_MISMATCH, "reward_response_mismatch")
        if isinstance(decoded, dict) and decoded.get("status") == "complete":
            return _validate_complete(observed)
        ready = _validate_ready(observed)
        if ready["decision_id"] == prior_decision_id:
            fail(EXIT_MISMATCH, "reward_decision_not_advanced")
        return ready
    fail(EXIT_MISMATCH, "post_reward_state_timeout")


def _same_player(left: dict[str, int], right: dict[str, int]) -> bool:
    return left == right


def _validate_transition(
    before: dict[str, object],
    after: dict[str, object],
    action: dict[str, object],
) -> None:
    before_player = before["player"]
    after_player = after["player"]
    kind = action["kind"]
    if kind == "discard_potion":
        slot=action["potion_slot"];old=before.get("potion_slots");new=after.get("potion_slots")
        expected=list(old) if old is not None else []
        if not 0<=slot<len(expected):fail(EXIT_MISMATCH,"potion_discard_reconciliation_failed")
        expected[slot]=None
        if after["screen_kind"]!="rewards" or before_player!=after_player or new!=expected or before["rewards"]!=after["rewards"]:
            fail(EXIT_MISMATCH,"potion_discard_reconciliation_failed")
    elif kind == "claim_gold":
        reward = before["rewards"][int(action["reward_slot"])]
        expected = dict(before_player)
        expected["gold"] += int(reward["gold_amount"])
        if after["screen_kind"] != "rewards" or after_player != expected:
            fail(EXIT_MISMATCH, "gold_claim_reconciliation_failed")
    elif kind == "collect_item":
        reward = before["rewards"][int(action["reward_slot"])]
        remaining = [r for r in after.get("rewards", []) if r["reward_index"] == reward["reward_index"]]
        expected=dict(before_player)
        expected["hp"]=min(expected["max_hp"],expected["hp"]+reward.get("heal_amount",0))
        if (after["screen_kind"] != "rewards" or expected != after_player or
                any(r["successfully_selected"] is not True or any(r.get(k) != reward.get(k) for k in
                    ("kind", "gold_amount", "cards", "card_selection_can_skip", "item_key", "potion_capacity_gain", "heal_amount")) for r in remaining)):
            fail(EXIT_MISMATCH, "item_claim_reconciliation_failed")
    elif kind == "claim_special_card":
        expected = dict(before_player)
        expected["deck_count"] += 1
        reward = before["rewards"][int(action["reward_slot"])]
        remaining = [r for r in after.get("rewards", []) if r["reward_index"] == reward["reward_index"]]
        if (after["screen_kind"] != "rewards" or after_player != expected or
                any(r["successfully_selected"] is not True or any(r[k] != reward[k] for k in
                    ("kind", "gold_amount", "cards", "card_selection_can_skip")) for r in remaining)):
            fail(EXIT_MISMATCH, "special_card_claim_reconciliation_failed")
    elif kind == "open_card":
        if after["screen_kind"] != "card_reward" or not _same_player(before_player, after_player):
            fail(EXIT_MISMATCH, "card_open_reconciliation_failed")
    elif kind == "choose_card":
        expected = dict(before_player)
        expected["deck_count"] += 1
        if after["screen_kind"] != "rewards" or after_player != expected:
            fail(EXIT_MISMATCH, "card_choice_reconciliation_failed")
    elif kind == "skip_card":
        if after["screen_kind"] != "rewards" or not _same_player(before_player, after_player):
            fail(EXIT_MISMATCH, "card_skip_reconciliation_failed")
    elif kind == "proceed":
        if after["screen_kind"] != "map" or not _same_player(before_player, after_player):
            fail(EXIT_MISMATCH, "reward_proceed_reconciliation_failed")
    else:
        fail(EXIT_MISMATCH, "reward_unknown_transition")

    if "potion_slots" in before and kind not in ("discard_potion", "proceed"):
        old = before["potion_slots"]
        new = after.get("potion_slots")
        if kind == "collect_item" and reward["kind"] == "potion":
            valid = isinstance(new, list) and len(new) == len(old)
            changes = [i for i in range(len(old)) if old[i] != new[i]] if valid else []
            valid = valid and len(changes) == 1 and old[changes[0]] is None and new[changes[0]] == reward["item_key"]
        elif kind == "collect_item" and reward.get("potion_capacity_gain",0)>0:
            valid = new == old + [None]*reward["potion_capacity_gain"]
        else:
            valid = new == old
        if not valid:
            fail(EXIT_MISMATCH, "item_claim_reconciliation_failed")

    if before.get("healing_rewards") and after["screen_kind"]!="map" and not after.get("healing_rewards"):
        fail(EXIT_MISMATCH,"reward_response_mismatch")

    if before.get("capacity_rewards") and after["screen_kind"]!="map" and not after.get("capacity_rewards"):
        fail(EXIT_MISMATCH,"reward_response_mismatch")

    if after["screen_kind"] != "map" and (
        int(after["decision_revision"]) != int(before["decision_revision"]) + 1
    ):
        fail(EXIT_MISMATCH, "reward_revision_mismatch")


def _run_apply_reward(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
    diagnostics: RewardActionDiagnostics | None = None,
) -> dict[str, object]:
    deadline = time.monotonic() + _APPLY_DEADLINE_SECONDS
    try:
        health = _read_body("health", probe._BASE_ROUTES[0][1], credential, connector, deadline)
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = _read_body("manifest", probe._BASE_ROUTES[1][1], credential, connector, deadline)
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        initial_body = _read_body(
            "reward",
            probe._REWARD_ROUTE[0][1],
            credential,
            connector,
            deadline,
        )
        if initial_body in (_REWARD_WAITING, _REWARD_UNSUPPORTED):
            fail(EXIT_MISMATCH, "reward_not_ready")
        initial = _validate_ready(initial_body)
        state = initial
        applied: list[dict[str, object]] = []
        claimed_gold = 0
        selected_cards: list[str] = []
        collected_items: list[dict[str, object]] = []

        while state["screen_kind"] != "map":
            if len(applied) >= _MAXIMUM_ACCEPTED_ACTIONS:
                fail(EXIT_MISMATCH, "reward_action_budget_exhausted")
            action = _choose_action(state, decision_provider)
            action_id = str(action["action_id"])
            decision_id = str(state["decision_id"])
            chosen_card: str | None = None
            if action["kind"] == "claim_gold":
                reward = state["rewards"][int(action["reward_slot"])]
                claimed_gold += int(reward["gold_amount"])
            elif action["kind"] == "claim_special_card":
                chosen_card = str(state["rewards"][int(action["reward_slot"])]["cards"][0])
            elif action["kind"] == "choose_card":
                chosen_card = str(state["rewards"][0]["cards"][int(action["card_slot"])])

            action_body = _read_reward_action_body(
                credential, connector, deadline, decision_id, action_id,
                str(action["kind"]), diagnostics,
            )
            if diagnostics is not None:
                diagnostics.inspect_receipt(action_body, decision_id, action_id)
            try:
                _validate_action_response(action_body, decision_id, action_id)
            except RecursionError:
                # The diagnostic parser treats deeply nested JSON as malformed;
                # retain the legacy receipt-mismatch result rather than surfacing it.
                fail(EXIT_MISMATCH, "reward_action_response_mismatch")
            if diagnostics is not None:
                diagnostics.accepted_receipt()
            try:
                after = _poll_next(credential, connector, deadline, decision_id)
                _validate_transition(state, after, action)
            except ToolFailure:
                if diagnostics is not None:
                    diagnostics.reconciliation_failure()
                raise
            if diagnostics is not None:
                diagnostics.reconciled_action()
            applied.append(
                {
                    "action_id": action_id,
                    "kind": action["kind"],
                    "decision_revision": state["decision_revision"],
                    "chosen_card": chosen_card,
                }
            )
            if chosen_card is not None:
                selected_cards.append(chosen_card)
            if action["kind"] == "collect_item":
                reward = state["rewards"][int(action["reward_slot"])]
                collected_items.append({"kind": reward["kind"], "key": reward["item_key"], "reward_index": reward["reward_index"]})
            state = after

        return {
            "schema_version": 1,
            "status": "passed",
            "milestone": "r0i_reward_resolution",
            "decision_provider": decision_provider,
            "applied": applied,
            "claimed_gold": claimed_gold,
            "selected_cards": selected_cards,
            "collected_items": collected_items,
            "before": initial,
            "after": state,
            "routes_checked": 3 + 2 * len(applied),
        }
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_reward(credential, provider, probe._literal_loopback_connector)
    finally:
        probe._zero(credential)


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
