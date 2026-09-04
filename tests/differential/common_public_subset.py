"""Offline H4 comparator; deliberately not a backend, actor view, or evidence gate.

Only public DTOs enter this helper. Local action IDs are used to look up an
advertised action and then discarded. Candidate bags retain multiplicity, but
cannot establish entity correspondence or legality beyond the advertised set.
No receipt (especially combat's queued receipt) proves a post-state here.
"""

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from game.backends.live import r0i_wire as wire
from game.contracts.headless_v0 import PolicyView


COMMON_SUBSET = {
    "combat": (
        "player.hp", "player.max_hp", "player.block", "player.energy",
        "enemy_vitals", "hand_count", "candidate_bag",
    ),
    "reward": (
        "player.hp", "player.max_hp", "player.gold", "player.deck_size",
        "reward_bag", "candidate_bag",
    ),
    "map": ("destination_kinds", "candidate_bag"),
    "room": ("room_kind", "candidate_bag"),
}

# These are explicit exclusions, never values silently filled into either DTO.
OMISSIONS = {
    "all": (
        "run/sequence/decision/hash/snapshot identity: separate control contracts",
        "receipts, authorization, revisions, public scopes and event sequence",
        "entity correspondence: no accepted cross-contract definition/instance map",
        "candidate order: compare a multiset, not list positions or action IDs",
    ),
    "combat": (
        "round versus turn: no accepted timing correspondence",
        "card/enemy IDs, upgrades, card types and target types: unlike schemas",
        "cost: wire text versus headless integer, no coercion",
        "intents, statuses, strength, piles: unlike or absent representations",
        "which card/target a play selects: only targeted versus untargeted compared",
        "dead-enemy retention and combat-complete versus next-phase boundary",
    ),
    "reward": (
        "card definitions/upgrades and selected offer identity: no accepted map",
        "opened state/reward index/slot: different screen and persistent-list models",
        "card amount: wire null versus headless structural zero, not equalized",
        "can_skip and visible offer count compared as advertised; timing may diverge",
    ),
    "map": (
        "coordinates/destination identity absent headlessly; graph/history absent on wire",
        "player vitals absent on map wire",
        "monster/rest_site aliases are category aliases only, not content parity",
    ),
    "room": (
        "player vitals, heal/effect amounts and effect kinds absent on room wire",
        "option/stable identity and dangerous/unsupported options not shared",
        "rest_site/rest alias is category-only; event options compare category only",
    ),
}


def typed(value: Any) -> tuple:
    """Type-exact deterministic key: bool/int/text/null and absence stay distinct."""
    if value is None:
        return ("null",)
    if type(value) in (bool, int, str):
        return (type(value).__name__, value)
    if type(value) is tuple:
        return ("tuple", tuple(typed(item) for item in value))
    raise TypeError("unsupported normalized public value")


def bag(values) -> tuple:
    return tuple(sorted(values, key=typed))


@dataclass(frozen=True)
class Boundary:
    family: str
    fields: Mapping[str, Any]
    selected_action: tuple | None
    selected_action_multiplicity: int

    def __post_init__(self):
        allowed = {"status", *COMMON_SUBSET.get(self.family, ())}
        if set(self.fields) - allowed:
            raise ValueError("unknown normalized field")
        for value in self.fields.values():
            typed(value)
        if self.selected_action is not None:
            typed(self.selected_action)
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


def _boundary(family, status, fields, candidates, selected_id):
    selected = None
    multiplicity = 0
    if candidates is not None:
        fields["candidate_bag"] = bag(candidates.values())
        if selected_id is not None:
            if selected_id not in candidates:
                raise ValueError("selected action was not advertised")
            selected = candidates[selected_id]
            multiplicity = Counter(candidates.values())[selected]
    elif selected_id is not None:
        raise ValueError("inactive boundary cannot select an action")
    return Boundary(family, {"status": status, **fields}, selected, multiplicity)


def _player(source, names):
    return {"player." + target: source[key] for key, target in names}


def _node_kind(kind):
    return {"monster": "combat", "rest_site": "rest"}.get(kind, kind)


def normalize_wire(decision: wire.Decision, selected_id: str | None = None) -> Boundary:
    # Constructors alone are not validators for this wire DTO.
    decision = wire.parse_decision(wire.encode_decision(decision))
    family, data = decision.family, decision.fields
    if decision.status != "ready":
        # complete has endpoint-specific semantics; never pretend it is terminal.
        return _boundary(family, decision.status, {}, None, selected_id)
    fields = {}
    if family == "combat":
        fields.update(_player(data["player"], ((k, k) for k in ("hp", "max_hp", "block", "energy"))))
        fields["enemy_vitals"] = bag(tuple(e[k] for k in ("hp", "max_hp", "block")) for e in data["enemies"])
        fields["hand_count"] = len(data["hand"])
    elif family == "reward":
        fields.update(_player(data["player"], (("hp", "hp"), ("max_hp", "max_hp"), ("gold", "gold"), ("deck_count", "deck_size"))))
        fields["reward_bag"] = bag(
            (r["kind"], r["successfully_selected"], r["gold_amount"])
            if r["kind"] == "gold" else
            (r["kind"], r["successfully_selected"], r["card_selection_can_skip"], len(r["cards"]))
            for r in data["rewards"]
        )
    elif family == "map":
        fields["destination_kinds"] = bag(_node_kind(c["kind"]) for c in data["candidates"])
    elif family == "room":
        fields["room_kind"] = _node_kind(data["screen_kind"])
    candidates = {}
    for action in data["legal_actions"]:
        kind = action["kind"]
        if family == "combat":
            semantics = (kind, action["target_index"] is not None) if kind == "play_card" else (kind,)
        elif family == "reward":
            semantics = ("open_card_reward",) if kind == "open_card" else (kind,)
            if kind == "claim_gold":
                semantics += (data["rewards"][action["reward_slot"]]["gold_amount"],)
        elif family == "map":
            semantics = ("choose_node", _node_kind(data["candidates"][action["candidate_index"]]["kind"]))
        else:
            candidate = data["candidates"][action["candidate_index"]]
            semantics = (candidate["kind"],)
        if action["action_id"] in candidates:
            raise ValueError("duplicate advertised action")
        candidates[action["action_id"]] = semantics
    return _boundary(family, "actionable", fields, candidates, selected_id)


def normalize_headless(view: PolicyView, selected_id: str | None = None) -> Boundary:
    if type(view) is not PolicyView:
        raise TypeError("only headless PolicyView is accepted")
    family, data = view.phase.value, view.observation.data
    if view.status.value != "actionable":
        return _boundary(family, view.status.value, {}, None, selected_id)
    fields = {}
    if family == "combat":
        fields.update(_player(data["player"], ((k, k) for k in ("hp", "max_hp", "block", "energy"))))
        fields["enemy_vitals"] = bag(tuple(e[k] for k in ("hp", "max_hp", "block")) for e in data["enemies"])
        fields["hand_count"] = len(data["hand"])
    elif family == "reward":
        fields.update(_player(data["player"], ((k, k) for k in ("hp", "max_hp", "gold", "deck_size"))))
        fields["reward_bag"] = bag(
            (r["kind"], r["claimed"], r["amount"]) if r["kind"] == "gold" else
            (r["kind"], r["claimed"], r["can_skip"], len(r["offers"]))
            for r in data["rewards"]
        )
    elif family == "map":
        fields["destination_kinds"] = bag(n["kind"] for n in data["nodes"] if n["available"])
    elif family == "room":
        fields["room_kind"] = data["room_kind"]
    candidates = {}
    for candidate in view.candidates:
        kind = candidate.kind.value.split(".")[1]
        semantics = (kind,)
        if kind == "play_card":
            semantics += (candidate.target_ref is not None,)
        elif kind == "claim_gold":
            semantics += (candidate.amount,)
        elif kind == "choose_node":
            semantics += (next(n["kind"] for n in data["nodes"] if n["node_ref"] == candidate.node_ref),)
        candidates[candidate.candidate_id] = semantics
    return _boundary(family, view.status.value, fields, candidates, selected_id)


@dataclass(frozen=True)
class Finding:
    path: str
    outcome: str
    reason: str


@dataclass(frozen=True)
class Comparison:
    outcome: str
    findings: tuple[Finding, ...]
    omissions: tuple[str, ...]
    evidence: str = "structural_fixture"
    live_capture: str = "unobserved"


def compare_case(wire_pre: Boundary, headless_pre: Boundary,
                 wire_post: Boundary | None, headless_post: Boundary | None) -> Comparison:
    """Passed means ONLY all declared compared dimensions matched synthetically.

    Any missing required dimension is unobserved (even absent on both sides).
    A mismatch takes precedence over unobserved, which takes precedence over
    passed. Diagnostics contain fixed paths/reasons, never raw payload values.
    """
    findings = []
    for stage, left, right in (("pre", wire_pre, headless_pre), ("post", wire_post, headless_post)):
        if left is None or right is None:
            findings.append(Finding(stage, "unobserved", "boundary_not_supplied"))
            continue
        if left.family != right.family:
            findings.append(Finding(stage + ".family", "divergent", "different_boundary_families"))
            continue
        for key in ("status", *COMMON_SUBSET.get(left.family, ())):
            if key not in left.fields or key not in right.fields:
                outcome, reason = "unobserved", "field_absent"
            elif typed(left.fields[key]) != typed(right.fields[key]):
                outcome, reason = "divergent", "typed_value_mismatch"
            else:
                outcome, reason = "passed", "equal_in_declared_subset"
            findings.append(Finding(stage + "." + key, outcome, reason))
    left_action, right_action = wire_pre.selected_action, headless_pre.selected_action
    if left_action is None or right_action is None:
        findings.append(Finding("action", "unobserved", "action_not_supplied"))
    else:
        outcome = "passed" if typed(left_action) == typed(right_action) else "divergent"
        findings.append(Finding("action", outcome, "advertised_category_only"))
    families = {b.family for b in (wire_pre, headless_pre, wire_post, headless_post) if b is not None}
    omissions = OMISSIONS["all"] + tuple(o for f in sorted(families) for o in OMISSIONS.get(f, ()))
    if max(wire_pre.selected_action_multiplicity, headless_pre.selected_action_multiplicity) > 1:
        omissions += ("selected category aliases multiple advertised candidates; entity identity unobserved",)
    outcomes = {f.outcome for f in findings}
    outcome = "divergent" if "divergent" in outcomes else "unobserved" if "unobserved" in outcomes else "passed"
    return Comparison(outcome, tuple(findings), omissions)
