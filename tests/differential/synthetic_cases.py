"""Project-authored R0i bodies paired with bounded real reduced-backend steps.

The wire side is an independent, static construction, not a conversion of the
headless output. It is encoder-valid synthetic data, not an observed game trace.
Fixture-local action positions never assert persistent or cross-contract IDs.
"""

from dataclasses import dataclass

from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.backends.live import r0i_wire as wire
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import ActionRequest, HeadlessBinding

from common_public_subset import Boundary, normalize_headless, normalize_wire


@dataclass(frozen=True)
class Case:
    name: str
    expected: str
    wire_pre: Boundary
    headless_pre: Boundary
    wire_post: Boundary | None
    headless_post: Boundary | None


def wire_decision(family, **fields):
    cls = {"combat": wire.CombatDecision, "reward": wire.RewardDecision,
           "map": wire.MapDecision, "room": wire.RoomDecision}[family]
    dto = cls(family, "ready", True, wire.BridgeBinding(wire.PROTOCOL, "0" * 64), fields)
    return wire.parse_decision(wire.encode_decision(dto))


def combat_body(*, defended=False, hp=60):
    # Fixed seed-7 structural setup; each card label is deliberately synthetic.
    targeted = [False, True, True, False, False]
    if defended:
        targeted = targeted[1:]
    hand = [{"hand_index": i, "id": "SYNTHETIC_CARD", "type": "Attack" if target else "Skill",
             "cost": "1", "target_type": "AnyEnemy" if target else "Self", "playable": True}
            for i, target in enumerate(targeted)]
    actions = [{"action_id": f"play:{i}:0" if target else f"play:{i}", "kind": "play_card",
                "hand_index": i, "target_index": 0 if target else None} for i, target in enumerate(targeted)]
    actions.append({"action_id": "end_turn", "kind": "end_turn", "hand_index": None, "target_index": None})
    return wire_decision("combat", round=1,
                         player={"hp": hp, "max_hp": 80, "block": 5 if defended else 0, "energy": 2 if defended else 3},
                         enemies=[{"index": 0, "id": "SYNTHETIC_ENEMY", "hp": 1, "max_hp": 1, "block": 0, "intents": ["Attack"]}],
                         hand=hand, legal_actions=actions)


def reward_body(stage):
    # Bridge parent always advertises proceed; headless initially does not.
    gold_claimed = stage != "initial"
    resolved = stage in ("chosen", "skipped")
    gold = {"reward_slot": 0, "reward_index": 0, "kind": "gold", "successfully_selected": gold_claimed,
            "gold_amount": 25, "cards": [], "card_selection_can_skip": False}
    card = {"reward_slot": 1, "reward_index": 1, "kind": "card", "successfully_selected": resolved,
            "gold_amount": None, "cards": ["SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"],
            "card_selection_can_skip": not resolved}
    rewards = [gold, card]
    actions = []
    if stage == "opened":
        card["reward_slot"] = 0
        rewards = [card]
        actions = [{"action_id": f"choose:{i}", "kind": "choose_card", "reward_slot": None, "card_slot": i} for i in range(3)]
        actions.append({"action_id": "skip_card", "kind": "skip_card", "reward_slot": None, "card_slot": None})
    else:
        if not gold_claimed:
            actions.append({"action_id": "claim:0", "kind": "claim_gold", "reward_slot": 0, "card_slot": None})
        if not resolved:
            actions.append({"action_id": "open:1", "kind": "open_card", "reward_slot": 1, "card_slot": None})
        actions.append({"action_id": "proceed", "kind": "proceed", "reward_slot": None, "card_slot": None})
    return wire_decision("reward", decision_revision=0, screen_kind="card_reward" if stage == "opened" else "rewards",
                         player={"hp": 60, "max_hp": 80, "gold": 25 if gold_claimed else 0, "deck_count": 11 if stage == "chosen" else 10},
                         rewards=rewards, legal_actions=actions)


def map_body(*, after_room=False):
    # R0i has no event category; preserve unknown rather than guessing an alias.
    kinds = ["monster"] if after_room else ["rest_site", "unknown"]
    return wire_decision("map", screen_kind="map", destination=None,
                         candidates=[{"candidate_index": i, "col": i, "row": 1, "kind": kind} for i, kind in enumerate(kinds)],
                         legal_actions=[{"action_id": f"select:{i}", "kind": "select_map_node", "candidate_index": i} for i in range(len(kinds))])


def room_body(*, event=False, proceed=False, optional_proceed=False):
    kinds = ["event_option"] if event else ["proceed"] if proceed else ["rest_heal"]
    if optional_proceed:
        kinds.append("proceed")
    candidates = [{"candidate_index": i, "action_id": "proceed" if kind == "proceed" else f"choose:{i}",
                   "kind": kind, "stable_id": "synthetic_option", "enabled": True, "supported": True,
                   "is_proceed": kind == "proceed", "is_dangerous": False} for i, kind in enumerate(kinds)]
    return wire_decision("room", screen_kind="event" if event else "rest_site",
                         phase="choose_or_proceed" if optional_proceed else "proceed" if proceed else "choose_option",
                         room_ordinal=1, candidates=candidates,
                         legal_actions=[{"action_id": c["action_id"], "kind": "proceed_room" if c["is_proceed"] else "choose_room_option",
                                         "candidate_index": c["candidate_index"]} for c in candidates])


def setup_backend():
    backend = ReducedRunBackend()
    backend.reset(HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, 7,
                                   {"initial_hp": 60, "combat_settings": {"enemy_max_hp": 1}}))
    return backend


def pick(decision, kind, *, card=None, node=None):
    candidates = [c for c in decision.candidates if c.kind.value == kind]
    if card is not None:
        refs = {c["card_ref"] for c in decision.observation.data["hand"] if c["card_definition_id"] == card}
        candidates = [c for c in candidates if c.card_ref in refs]
    if node is not None:
        refs = {n["node_ref"] for n in decision.observation.data["nodes"] if n["kind"] == node}
        candidates = [c for c in candidates if c.node_ref in refs]
    return candidates[0]


def advance(backend, kind, **kwargs):
    decision = backend.observe()
    candidate = pick(decision, kind, **kwargs)
    transition = backend.apply(ActionRequest(HeadlessBinding.for_candidate(decision, candidate.candidate_id)))
    assert transition.result.value == "accepted"
    return normalize_headless(decision.policy_view(), candidate.candidate_id), normalize_headless(transition.next_decision.policy_view())


def make_cases():
    cases = []
    backend = setup_backend()
    try:
        pre, post = advance(backend, "combat.play_card", card="defend")
        cases.append(Case("combat_defend_common_vitals", "passed", normalize_wire(combat_body(), "play:0"), pre,
                          normalize_wire(combat_body(defended=True)), post))
        cases.append(Case("combat_defend_hp_divergence", "divergent", normalize_wire(combat_body(), "play:0"), pre,
                          normalize_wire(combat_body(defended=True, hp=59)), post))
    finally:
        backend.close()
    backend = setup_backend()
    try:
        pre, post = advance(backend, "combat.end_turn")
        cases.append(Case("combat_queued_without_post", "unobserved", normalize_wire(combat_body(), "end_turn"), pre, None, post))
    finally:
        backend.close()
    for branch in ("rest", "event"):
        backend = setup_backend()
        try:
            pre, post = advance(backend, "combat.play_card", card="strike")
            if branch == "rest":
                cases.append(Case("combat_to_reward_structural_gap", "divergent", normalize_wire(combat_body(), "play:2:0"), pre,
                                  normalize_wire(reward_body("initial")), post))
            for kind, wire_action, before, after in (
                ("reward.claim_gold", "claim:0", "initial", "gold"),
                ("reward.open_card_reward", "open:1", "gold", "opened"),
                ("reward.choose_card" if branch == "rest" else "reward.skip_card", "choose:0" if branch == "rest" else "skip_card", "opened", "chosen" if branch == "rest" else "skipped"),
            ):
                pre, post = advance(backend, kind)
                cases.append(Case(branch + "_" + kind, "divergent", normalize_wire(reward_body(before), wire_action), pre,
                                  normalize_wire(reward_body(after)), post))
            pre, post = advance(backend, "reward.proceed")
            cases.append(Case(branch + "_reward_proceed_map_gap", "divergent", normalize_wire(reward_body("chosen" if branch == "rest" else "skipped"), "proceed"), pre,
                              normalize_wire(map_body()), post))
            pre, post = advance(backend, "map.choose_node", node=branch)
            cases.append(Case(branch + "_map_event_category_gap", "divergent", normalize_wire(map_body(), "select:0" if branch == "rest" else "select:1"), pre,
                              normalize_wire(room_body(event=branch == "event")), post))
            pre, post = advance(backend, "room.rest_heal" if branch == "rest" else "room.event_option")
            cases.append(Case(branch + "_room_action", "passed" if branch == "rest" else "divergent", normalize_wire(room_body(event=branch == "event"), "choose:0"), pre,
                              normalize_wire(room_body(event=branch == "event", proceed=branch == "rest")), post))
            if branch == "rest":
                cases.append(Case("rest_optional_proceed_gap", "divergent", normalize_wire(room_body(optional_proceed=True), "choose:0"), pre,
                                  normalize_wire(room_body(proceed=True)), post))
                pre, post = advance(backend, "room.proceed")
                cases.append(Case("rest_proceed_to_combat_map", "passed", normalize_wire(room_body(proceed=True), "proceed"), pre,
                                  normalize_wire(map_body(after_room=True)), post))
                pre, post = advance(backend, "map.choose_node", node="combat")
                cases.append(Case("map_monster_no_post_capture", "unobserved", normalize_wire(map_body(after_room=True), "select:0"), pre, None, post))
        finally:
            backend.close()
    return tuple(cases)


def fixture_bodies():
    """Named byte corpus hashed independently of comparator output."""
    return {
        "combat_initial": wire.encode_decision(combat_body()),
        "combat_defended": wire.encode_decision(combat_body(defended=True)),
        "combat_hp_divergent": wire.encode_decision(combat_body(defended=True, hp=59)),
        **{"reward_" + stage: wire.encode_decision(reward_body(stage)) for stage in ("initial", "gold", "opened", "chosen", "skipped")},
        "map_initial": wire.encode_decision(map_body()),
        "map_after_room": wire.encode_decision(map_body(after_room=True)),
        "rest_heal": wire.encode_decision(room_body()),
        "rest_proceed": wire.encode_decision(room_body(proceed=True)),
        "rest_optional_proceed": wire.encode_decision(room_body(optional_proceed=True)),
        "event_option": wire.encode_decision(room_body(event=True)),
    }
