"""Frozen, public-only variable-candidate encoding for ``headless_v0``.

This module deliberately embeds the accepted ``headless_encoding_v1`` schema.
It consumes only a validated :class:`PolicyView`; opaque references are used
briefly to copy public entity fields into candidate rows and are never emitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    CONTRACT_VERSION,
    CandidateKind,
    PolicyView,
    PublicEvent,
    canonical_json_bytes,
    candidate_from_dict,
    candidate_to_dict,
)


class HeadlessEncodingError(ValueError):
    """Raised when a public view or encoded record violates the frozen schema."""


ENCODING_VERSION = "headless_encoding_v1"
_SCHEMA_VERSION = "headless_encoding_v1.schema.v1"
_SOURCE_CONTRACT_FINGERPRINT = "e5ab4c29f0c077178d543b36e24494d3ec8d0d62528f44becf6f13eae7dee1b3"
_CONTENT_FINGERPRINT = "fe771ea0f82c114d1d6a6389a44b169525c047914d955ce49d6db54e2472230f"
_CANDIDATE_ID = re.compile(r"cand\.[0-9a-f]{64}\Z")

_REGISTRIES: dict[str, tuple[str, ...]] = {
    "status": ("actionable", "waiting", "terminal", "unsupported"),
    "phase": ("combat", "reward", "map", "room", "terminal", "unsupported"),
    "candidate_kind": (
        "combat.play_card", "combat.end_turn", "reward.claim_gold",
        "reward.open_card_reward", "reward.choose_card", "reward.skip_card",
        "reward.proceed", "map.choose_node", "room.rest_heal",
        "room.event_option", "room.proceed",
    ),
    "public_event_kind": (
        "combat.card_played", "combat.turn_ended", "combat.resolved",
        "reward.gold_claimed", "reward.card_opened", "reward.card_chosen",
        "reward.card_skipped", "reward.proceeded", "map.node_chosen",
        "room.rest_healed", "room.event_option_chosen", "room.proceeded",
        "run.terminated",
    ),
    "combat_outcome": ("none", "ongoing", "victory", "defeat"),
    "event_outcome": ("none", "ongoing", "victory", "defeat", "abandoned"),
    "run_outcome": ("none", "victory", "defeat", "abandoned"),
    "unsupported_reason": (
        "none", "unsupported_phase", "unsupported_content", "unsupported_rule",
        "backend_unavailable",
    ),
    "reward_kind": ("none", "gold", "card"),
    "node_kind": ("none", "combat", "rest", "event", "terminal"),
    "room_kind": ("none", "rest", "event"),
    "room_option_kind": ("none", "rest_heal", "event_option"),
    "room_effect_kind": ("none", "heal", "gain_gold", "lose_hp"),
    "intent_kind": ("none", "attack", "defend", "attack_defend", "buff", "debuff", "shuffle"),
    "status_kind": ("none", "vulnerable", "shrink"),
}
_SEMANTICS = (
    "bash", "body_slam", "defend", "fuzzy_wurm_crawler", "iron_wave",
    "leaf_slime_m", "leaf_slime_s", "mawler", "nibbit", "pommel_strike",
    "shrinker_beetle", "shrug_it_off", "simple_enemy", "slimed", "strike",
    "twig_slime_m", "twig_slime_s", "__unknown__",
)


def _features() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    global_names = (
        tuple(f"status.{item}" for item in _REGISTRIES["status"])
        + tuple(f"phase.{item}" for item in _REGISTRIES["phase"])
        + ("player.present", "player.hp", "player.max_hp", "player.gold", "player.deck_size",
           "player.block", "player.energy", "player.energy_per_turn", "player.strength",
           "player.status_vulnerable", "player.status_shrink", "combat.turn",
           "combat.draw_pile_size", "combat.discard_pile_size", "combat.exhaust_pile_size",
           "combat.terminal")
        + tuple(f"combat.outcome.{item}" for item in _REGISTRIES["combat_outcome"])
        + ("reward.can_proceed", "map.has_current_node", "map.edge_count",
           "map.visited_node_count", "room.can_proceed")
        + tuple(f"room.kind.{item}" for item in _REGISTRIES["room_kind"])
        + tuple(f"terminal.outcome.{item}" for item in _REGISTRIES["run_outcome"])
        + tuple(f"unsupported.reason.{item}" for item in _REGISTRIES["unsupported_reason"])
    )
    entity_names = (
        tuple(f"entity.{item}" for item in ("card", "enemy", "reward", "offer", "node", "option"))
        + tuple(f"card_definition.{item}" for item in _SEMANTICS)
        + tuple(f"enemy_definition.{item}" for item in _SEMANTICS)
        + tuple(f"reward_kind.{item}" for item in _REGISTRIES["reward_kind"])
        + tuple(f"node_kind.{item}" for item in _REGISTRIES["node_kind"])
        + tuple(f"option_kind.{item}" for item in _REGISTRIES["room_option_kind"])
        + tuple(f"effect.{item}" for item in _REGISTRIES["room_effect_kind"])
        + tuple(f"intent.{item}" for item in _REGISTRIES["intent_kind"])
        + tuple(f"intent_status.{item}" for item in _REGISTRIES["status_kind"])
        + ("alive", "card_upgraded", "reward_claimed", "reward_opened", "reward_can_skip",
           "node_available", "node_visited", "option_enabled", "hp", "max_hp", "block",
           "strength", "status_vulnerable", "status_shrink", "intent_attack_count",
           "intent_attack_damage", "intent_block_gain", "intent_slimed_added",
           "intent_status_stacks", "intent_strength_gain", "card_cost", "reward_amount",
           "option_amount")
    )
    event_names = (
        tuple(f"event_kind.{item}" for item in _REGISTRIES["public_event_kind"])
        + tuple(f"event_phase.{item}" for item in _REGISTRIES["phase"])
        + ("sequence", "has_card_definition")
        + tuple(f"card_definition.{item}" for item in _SEMANTICS)
        + ("has_target_enemy_definition",)
        + tuple(f"target_enemy_definition.{item}" for item in _SEMANTICS)
        + tuple(f"outcome.{item}" for item in _REGISTRIES["event_outcome"])
        + tuple(f"node_kind.{item}" for item in _REGISTRIES["node_kind"])
        + tuple(f"effect.{item}" for item in _REGISTRIES["room_effect_kind"])
        + ("has_amount", "amount", "has_offer_count", "offer_count", "has_upgraded", "upgraded")
    )
    candidate_names = tuple(f"candidate_kind.{item}" for item in _REGISTRIES["candidate_kind"])
    for component in ("card", "target_enemy", "reward", "offer", "node", "option"):
        candidate_names += (f"{component}.present",) + tuple(f"{component}.{item}" for item in entity_names)
    return global_names, entity_names, event_names, candidate_names


GLOBAL_FEATURE_NAMES, ENTITY_FEATURE_NAMES, PUBLIC_EVENT_FEATURE_NAMES, CANDIDATE_FEATURE_NAMES = _features()
assert tuple(map(len, (GLOBAL_FEATURE_NAMES, ENTITY_FEATURE_NAMES, PUBLIC_EVENT_FEATURE_NAMES, CANDIDATE_FEATURE_NAMES))) == (47, 90, 78, 557)
_G = {name: index for index, name in enumerate(GLOBAL_FEATURE_NAMES)}
_E = {name: index for index, name in enumerate(ENTITY_FEATURE_NAMES)}
_V = {name: index for index, name in enumerate(PUBLIC_EVENT_FEATURE_NAMES)}


def _schema() -> dict[str, Any]:
    # Kept as data rather than read from the coordinator-owned JSON so installed
    # consumers carry their exact schema and fingerprint with the encoder.
    return {
        "schema_version": _SCHEMA_VERSION, "encoding_version": ENCODING_VERSION,
        "source_contract": {"version": "headless_v0", "fingerprint": _SOURCE_CONTRACT_FINGERPRINT},
        "content": {"version": "reduced_content_v0", "fingerprint": _CONTENT_FINGERPRINT},
        "feature_dimensions": {"global": 47, "entity": 90, "public_event": 78, "candidate": 557},
        "categorical_registries": {key: list(value) for key, value in _REGISTRIES.items()},
        "semantic_definition_vocabulary": list(_SEMANTICS),
        "global_feature_names": list(GLOBAL_FEATURE_NAMES),
        "entity_feature_names": list(ENTITY_FEATURE_NAMES),
        "public_event_feature_names": list(PUBLIC_EVENT_FEATURE_NAMES),
        "candidate_join_specs": [["combat.play_card", "card", "target_enemy_if_non_null"], ["combat.end_turn"], ["reward.claim_gold", "reward"], ["reward.open_card_reward", "reward"], ["reward.choose_card", "reward", "offer"], ["reward.skip_card", "reward"], ["reward.proceed"], ["map.choose_node", "node"], ["room.rest_heal", "option"], ["room.event_option", "option"], ["room.proceed"]],
        "normalization": {"boolean": "float(value) where value in {0,1}", "collection_count": "float(value)/128.0 for 0<=value<=128", "event_sequence": "float(value)/127.0 for 0<=value<=127", "hp": "float(value)/100000.0 for 0<=value<=100000", "max_hp": "float(value)/100000.0 for 1<=value<=100000", "contract_counter": "float(value)/1000000000.0 for 0<=value<=1000000000", "padding": "0.0; mask=false; never legal", "validation": "all emitted float coordinates finite and in [0.0,1.0]"},
        "collation": {"global_features": ["float32", "(B,47)"], "entity_features": ["float32", "(B,Emax,90)", 0], "public_event_features": ["float32", "(B,Vmax,78)", 0], "candidate_features": ["float32", "(B,Amax,557)", 0], "entity_mask": ["bool", "(B,Emax)"], "public_event_mask": ["bool", "(B,Vmax)"], "candidate_mask": ["bool", "(B,Amax)"], "candidate_ids": ["out_of_band_utf8", "(B,variable)"]},
        "candidate_feature_names": list(CANDIDATE_FEATURE_NAMES),
        "public_api": {"constants": ["ENCODING_VERSION", "ENCODING_FINGERPRINT", "GLOBAL_FEATURE_NAMES", "ENTITY_FEATURE_NAMES", "PUBLIC_EVENT_FEATURE_NAMES", "CANDIDATE_FEATURE_NAMES"], "exception": {"name": "HeadlessEncodingError", "base": "ValueError"}, "records": {"EncodedPolicyView": {"frozen": True, "slots": True, "fields": [["encoding_version", "str"], ["encoding_fingerprint", "str"], ["global_features", "tuple[float,...]"], ["entity_rows", "tuple[tuple[float,...],...]"], ["public_event_rows", "tuple[tuple[float,...],...]"], ["candidate_rows", "tuple[tuple[float,...],...]"], ["candidate_ids", "tuple[str,...]"]]}, "CollatedPolicyBatch": {"frozen": True, "slots": True, "fields": [["encoding_version", "str"], ["encoding_fingerprint", "str"], ["global_features", "numpy.ndarray"], ["entity_features", "numpy.ndarray"], ["public_event_features", "numpy.ndarray"], ["candidate_features", "numpy.ndarray"], ["entity_mask", "numpy.ndarray"], ["public_event_mask", "numpy.ndarray"], ["candidate_mask", "numpy.ndarray"], ["candidate_ids", "tuple[tuple[str,...],...]"]]}}, "functions": [["encoding_schema", "() -> Mapping[str,Any]"], ["encode_policy_view", "(view: PolicyView) -> EncodedPolicyView"], ["collate_policy_views", "(views: Sequence[EncodedPolicyView]) -> CollatedPolicyBatch"]]},
        "categorical_rules": {"one_hot": "Exactly one coordinate is 1.0 for every present categorical field; all other coordinates in its registry are 0.0.", "semantic_present": "Use the exact combined semantic_definition_vocabulary regardless of card/enemy domain; any syntactically valid unlisted ID selects __unknown__.", "semantic_absent": "All coordinates zero. Absence never selects __unknown__.", "global_inactive": "Outside combat activate combat.outcome.none; outside room activate room.kind.none; outside terminal activate terminal.outcome.none; outside unsupported activate unsupported.reason.none. All other context-inapplicable global fields zero.", "entity_inactive": "Only entity kind and fields present for that entity form are encoded. Inapplicable categorical groups are all-zero, including their none coordinate.", "event_inactive": "Absent payload categorical groups are all-zero, including their none coordinate. Corresponding has_* flags are zero. Present nullable target_enemy_definition_id=null is absence.", "real_none_values": "For a present room option/event effect with value none, effect.none=1. For a present enemy intent status_kind=none, intent_status.none=1. These are distinct from inactive all-zero groups.", "candidate_absent": "Each absent component has present=0 and all 90 copied entity coordinates zero; present components have present=1 and exact generic entity row.", "numeric_absent": "Absent numeric values and boolean fields are zero; presence is conveyed by entity/context/kind and explicit has_* flags where specified."},
        "row_order": {"batch": "Preserve the input Sequence[EncodedPolicyView] order exactly as the batch axis; never sort or regroup records.", "entities": {"combat": "Enemies in observation list order, then hand cards in observation list order.", "reward": "Each reward row followed immediately by its offer rows, in public list order.", "map": "Nodes in public list order.", "room": "Options in public list order.", "terminal": "No rows.", "unsupported": "No rows."}, "public_events": "Input public_events order; each event uses its own phase, payload and sequence, not current view phase.", "candidates": "Exactly view.candidates order. candidate_ids has the same length/order and is never a numeric/categorical feature.", "sorting": "Never introduce sorting by opaque references, scopes, hashes or IDs. Valid PolicyView may already canonicalize candidates by ID.", "aggregate_limits": "No extra aggregate row cap: nested reward offers and candidates may exceed 128 rows. Contract collection and public-event bounds remain authoritative."},
        "map_representation": {"mode": "summary_and_public_node_fields", "global_fields": {"has_current_node": "0.0 iff current_node_ref is null, else 1.0.", "edge_count": "len(edges)/128.0", "visited_node_count": "len(visited_node_refs)/128.0"}, "entities": "Each node retains kind, available and visited; candidate node joins copy those fields.", "excluded": "Current-node identity, edge endpoint identities/connectivity, and visited reference values are omitted. No graph reconstruction or reference-derived ordinal is encoded.", "disposition": "Explicit bounded lossy representation of the current public map form; not a reversible observation encoding."},
        "numeric_denominators": {"global": {"player.hp": 100000, "player.max_hp": 100000, "player.gold": 1000000000, "player.deck_size": 128, "player.block": 1000000000, "player.energy": 1000000000, "player.energy_per_turn": 1000000000, "player.strength": 1000000000, "player.status_vulnerable": 1000000000, "player.status_shrink": 1000000000, "combat.turn": 1000000000, "combat.draw_pile_size": 1000000000, "combat.discard_pile_size": 1000000000, "combat.exhaust_pile_size": 1000000000, "map.edge_count": 128, "map.visited_node_count": 128}, "entity": {"hp": 100000, "max_hp": 100000, "block": 1000000000, "strength": 1000000000, "status_vulnerable": 1000000000, "status_shrink": 1000000000, "intent_attack_count": 1000000000, "intent_attack_damage": 1000000000, "intent_block_gain": 1000000000, "intent_slimed_added": 1000000000, "intent_status_stacks": 1000000000, "intent_strength_gain": 1000000000, "card_cost": 1000000000, "reward_amount": 1000000000, "option_amount": 1000000000}, "public_event": {"sequence": 127, "amount": 1000000000, "offer_count": 128}, "candidate": "Each copied entity coordinate uses entity normalization; presence/kind are boolean/one-hot."},
        "entity_sources": {"card": {"source": "observation.hand", "fields": {"card_definition": "card_definition_id", "card_cost": "cost", "card_upgraded": "upgraded"}}, "enemy": {"source": "observation.enemies", "fields": {"enemy_definition": "enemy_definition_id", "alive": "alive", "hp": "hp", "max_hp": "max_hp", "block": "block", "strength": "strength", "status_vulnerable": "statuses.vulnerable", "status_shrink": "statuses.shrink", "intent": "intent.kind", "intent_status": "intent.status_kind", "intent_attack_count": "intent.attack_count", "intent_attack_damage": "intent.attack_damage", "intent_block_gain": "intent.block_gain", "intent_slimed_added": "intent.slimed_added", "intent_status_stacks": "intent.status_stacks", "intent_strength_gain": "intent.strength_gain"}}, "reward": {"source": "observation.rewards", "fields": {"reward_kind": "kind", "reward_amount": "amount", "reward_claimed": "claimed", "reward_opened": "opened", "reward_can_skip": "can_skip"}}, "offer": {"source": "observation.rewards[*].offers", "fields": {"card_definition": "card_definition_id", "card_upgraded": "upgraded"}}, "node": {"source": "observation.nodes", "fields": {"node_kind": "kind", "node_available": "available", "node_visited": "visited"}}, "option": {"source": "observation.options", "fields": {"option_kind": "kind", "effect": "effect", "option_amount": "amount", "option_enabled": "enabled"}}},
        "event_payload_sources": {"combat.card_played": {"card_definition": "card_definition_id", "target_enemy_definition": "target_enemy_definition_id"}, "combat.turn_ended": {}, "combat.resolved": {"outcome": "outcome"}, "reward.gold_claimed": {"amount": "amount"}, "reward.card_opened": {"offer_count": "offer_count"}, "reward.card_chosen": {"card_definition": "card_definition_id", "upgraded": "upgraded"}, "reward.card_skipped": {}, "reward.proceeded": {}, "map.node_chosen": {"node_kind": "node_kind"}, "room.rest_healed": {"amount": "amount"}, "room.event_option_chosen": {"amount": "amount", "effect": "effect"}, "room.proceeded": {}, "run.terminated": {"outcome": "outcome"}},
        "candidate_join_rules": {"scope": "Resolve references only inside the exact input view; joins never use backend or target/audit data.", "card": "combat.play_card.card_ref -> observation.hand.card_ref", "target_enemy": "Non-null combat.play_card.target_ref -> observation.enemies.enemy_ref; use the validated advertised living target.", "reward": "reward_ref -> observation.rewards.reward_ref for claim_gold/open_card_reward/choose_card/skip_card.", "offer": "offer_ref -> selected reward.offers.offer_ref for choose_card.", "node": "node_ref -> observation.nodes.node_ref for map.choose_node.", "option": "option_ref -> observation.options.option_ref for room.rest_heal/event_option.", "no_join": ["combat.end_turn", "reward.proceed", "room.proceed"], "output": "Copy the corresponding generic entity row; never emit a reference, row index, candidate index, scope or hash."},
        "empty_behavior": {"non_actionable": "WAITING, TERMINAL and UNSUPPORTED have candidate_rows=() and candidate_ids=(); observation and public events still encode normally.", "empty_batch": "B=0 is accepted: globals (0,47); entities (0,0,90); events (0,0,78); candidates (0,0,557); masks (0,0); candidate_ids=().", "empty_rows": "For nonempty batches, Emax/Vmax/Amax may independently be zero with exact zero-width shapes.", "padding": "Pad to each batch maximum with float32 0.0 and bool false. Every real row has mask true, even if its coordinates are all zero. No padded candidate ID.", "arrays": "Collation arrays are fresh independent NumPy arrays; public record fields are frozen. No Torch dependency."},
        "validation": {"input": "Accept only exact type PolicyView (not dict, duck type or subclass). Existing contract validation is authoritative; reject malformed types/joins/numerics rather than clipping or repairing.", "encoded_record": "Validate exact version/fingerprint, widths, finite normalized values in [0,1], candidate ID count/alignment, unique canonical cand.<64 lowercase hex> string IDs, tuple row structure. No implicit numeric coercion of malformed inputs.", "collation": "Accept only exact EncodedPolicyView records conforming to this schema. Reject mismatched version/fingerprint, ragged widths, NaN/Inf/out-of-range coordinates, wrong candidate ID counts and duplicate IDs.", "failure": "Public malformed input failures use HeadlessEncodingError; do not silently drop, normalize, clip or reorder malformed values.", "schema_accessor": "Return an independent schema value so caller mutation cannot change future schema values or exported fingerprint."},
        "information_boundary": {"allowed": "Only current public observation, advertised candidate payloads and current public-event tuple.", "forbidden": "No opaque refs, decision/candidate IDs, scopes, hashes, run/control IDs, row ordinals (except bounded public event sequence), backend-private state, target/audit records or future outcomes in numeric/categorical features.", "out_of_band": "candidate_ids is preserved verbatim solely for reversible action selection.", "metamorphic_oracle": "Construct valid reallocated views by recomputing public references and candidates under new history/reveal/decision scopes. Global rows and corresponding entity/event/candidate rows remain numerically identical modulo public row/candidate permutation; each view retains its own correctly aligned candidate IDs. Compare candidate semantics/multiset, not raw IDs."},
        "fingerprint": {"algorithm": "sha256", "domain_utf8": "headless_encoding_v1.schema.v1", "separator_byte": 0, "canonical_json": "Use game.contracts.headless_v0.canonical_json_bytes: UTF-8; sorted object keys; compact separators ',' and ':'; ensure_ascii=false; allow_nan=false; schema payload includes this fingerprint specification but no digest field."},
        "global_sources": {"status": "view.status.value, one-hot, for every view.", "phase": "view.phase.value, one-hot, for every view.", "player.present": "1.0 in combat/reward/map/room/terminal; 0.0 in unsupported.", "player.hp_and_max_hp": "observation.data.player.hp and max_hp in combat/reward/map/room/terminal; zero in unsupported.", "player.gold_and_deck_size": "observation.data.player.gold and deck_size in reward/map/room/terminal only; zero elsewhere.", "player.combat_stats": "In combat only, observation.data.player.block, energy, energy_per_turn and strength map to corresponding player.* names; statuses.vulnerable and statuses.shrink map to player.status_vulnerable and player.status_shrink. Zero elsewhere.", "combat": "In combat only, observation.data.turn, draw_pile_size, discard_pile_size, exhaust_pile_size, terminal and outcome map to corresponding combat.* names. Else numerical/boolean fields zero and combat.outcome.none=1.", "reward": "In reward only, observation.data.can_proceed maps to reward.can_proceed; zero elsewhere.", "map": "In map only, current_node_ref nullness, len(edges), and len(visited_node_refs) use exact map_representation.global_fields formulas; zero elsewhere.", "room": "In room only, observation.data.can_proceed and room_kind map to room.can_proceed and room.kind. Else can_proceed=0 and room.kind.none=1.", "terminal": "In terminal only, observation.data.outcome maps to terminal.outcome; else terminal.outcome.none=1.", "unsupported": "In unsupported only, observation.data.reason_code maps to unsupported.reason; else unsupported.reason.none=1."},
    }


_SCHEMA = _schema()
ENCODING_FINGERPRINT = sha256(
    b"headless_encoding_v1.schema.v1" + bytes((0,)) + canonical_json_bytes(_SCHEMA)
).hexdigest()
if ENCODING_FINGERPRINT != "3eee27f82ad803d1d47ac5d2ac6ba6fcce2d236f977fde589fe6ee38a9608fa1":
    raise RuntimeError("Embedded headless encoding schema does not match its accepted fingerprint.")


@dataclass(frozen=True, slots=True)
class EncodedPolicyView:
    encoding_version: str
    encoding_fingerprint: str
    global_features: tuple[float, ...]
    entity_rows: tuple[tuple[float, ...], ...]
    public_event_rows: tuple[tuple[float, ...], ...]
    candidate_rows: tuple[tuple[float, ...], ...]
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CollatedPolicyBatch:
    encoding_version: str
    encoding_fingerprint: str
    global_features: np.ndarray
    entity_features: np.ndarray
    public_event_features: np.ndarray
    candidate_features: np.ndarray
    entity_mask: np.ndarray
    public_event_mask: np.ndarray
    candidate_mask: np.ndarray
    candidate_ids: tuple[tuple[str, ...], ...]


def encoding_schema() -> Mapping[str, Any]:
    """Return a mutation-isolated copy of the accepted schema."""
    return json.loads(canonical_json_bytes(_SCHEMA).decode("utf-8"))


def _number(value: Any, denominator: int, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= denominator:
        raise HeadlessEncodingError(f"{path} is outside its accepted public bounds.")
    result = float(value) / float(denominator)
    if not math.isfinite(result):
        raise HeadlessEncodingError(f"{path} did not normalize to a finite value.")
    return result


def _boolean(value: Any, path: str) -> float:
    if type(value) is not bool:
        raise HeadlessEncodingError(f"{path} must be a bool.")
    return 1.0 if value else 0.0


def _one_hot(row: list[float], names: Mapping[str, int], prefix: str, value: str, registry: Sequence[str]) -> None:
    if value not in registry:
        raise HeadlessEncodingError(f"Unknown categorical value for {prefix}: {value!r}.")
    row[names[f"{prefix}.{value}"]] = 1.0


def _semantic(row: list[float], names: Mapping[str, int], prefix: str, value: Any) -> None:
    if not isinstance(value, str):
        raise HeadlessEncodingError(f"{prefix} must be a semantic identifier.")
    item = value if value in _SEMANTICS else "__unknown__"
    row[names[f"{prefix}.{item}"]] = 1.0


def _entity(kind: str, item: Mapping[str, Any]) -> tuple[float, ...]:
    row = [0.0] * 90
    _one_hot(row, _E, "entity", kind, ("card", "enemy", "reward", "offer", "node", "option"))
    if kind == "card":
        _semantic(row, _E, "card_definition", item["card_definition_id"])
        row[_E["card_cost"]] = _number(item["cost"], 1_000_000_000, "card.cost")
        row[_E["card_upgraded"]] = _boolean(item["upgraded"], "card.upgraded")
    elif kind == "enemy":
        _semantic(row, _E, "enemy_definition", item["enemy_definition_id"])
        for name, source, denominator in (("hp", "hp", 100_000), ("max_hp", "max_hp", 100_000), ("block", "block", 1_000_000_000), ("strength", "strength", 1_000_000_000), ("status_vulnerable", "vulnerable", 1_000_000_000), ("status_shrink", "shrink", 1_000_000_000)):
            value = item["statuses"][source] if source in ("vulnerable", "shrink") else item[source]
            row[_E[name]] = _number(value, denominator, f"enemy.{source}")
        row[_E["alive"]] = _boolean(item["alive"], "enemy.alive")
        intent = item["intent"]
        _one_hot(row, _E, "intent", intent["kind"], _REGISTRIES["intent_kind"])
        _one_hot(row, _E, "intent_status", intent["status_kind"], _REGISTRIES["status_kind"])
        for name, source in (("intent_attack_count", "attack_count"), ("intent_attack_damage", "attack_damage"), ("intent_block_gain", "block_gain"), ("intent_slimed_added", "slimed_added"), ("intent_status_stacks", "status_stacks"), ("intent_strength_gain", "strength_gain")):
            row[_E[name]] = _number(intent[source], 1_000_000_000, f"enemy.intent.{source}")
    elif kind == "reward":
        _one_hot(row, _E, "reward_kind", item["kind"], _REGISTRIES["reward_kind"])
        row[_E["reward_amount"]] = _number(item["amount"], 1_000_000_000, "reward.amount")
        for name, source in (("reward_claimed", "claimed"), ("reward_opened", "opened"), ("reward_can_skip", "can_skip")):
            row[_E[name]] = _boolean(item[source], f"reward.{source}")
    elif kind == "offer":
        _semantic(row, _E, "card_definition", item["card_definition_id"])
        row[_E["card_upgraded"]] = _boolean(item["upgraded"], "offer.upgraded")
    elif kind == "node":
        _one_hot(row, _E, "node_kind", item["kind"], _REGISTRIES["node_kind"])
        row[_E["node_available"]] = _boolean(item["available"], "node.available")
        row[_E["node_visited"]] = _boolean(item["visited"], "node.visited")
    else:
        _one_hot(row, _E, "option_kind", item["kind"], _REGISTRIES["room_option_kind"])
        _one_hot(row, _E, "effect", item["effect"], _REGISTRIES["room_effect_kind"])
        row[_E["option_amount"]] = _number(item["amount"], 1_000_000_000, "option.amount")
        row[_E["option_enabled"]] = _boolean(item["enabled"], "option.enabled")
    return tuple(row)


def _global(view: PolicyView) -> tuple[float, ...]:
    row = [0.0] * 47
    phase = view.phase.value
    _one_hot(row, _G, "status", view.status.value, _REGISTRIES["status"])
    _one_hot(row, _G, "phase", phase, _REGISTRIES["phase"])
    data = view.observation.data
    if phase != "unsupported":
        player = data["player"]
        row[_G["player.present"]] = 1.0
        row[_G["player.hp"]] = _number(player["hp"], 100_000, "player.hp")
        row[_G["player.max_hp"]] = _number(player["max_hp"], 100_000, "player.max_hp")
        if phase in ("reward", "map", "room", "terminal"):
            row[_G["player.gold"]] = _number(player["gold"], 1_000_000_000, "player.gold")
            row[_G["player.deck_size"]] = _number(player["deck_size"], 128, "player.deck_size")
    if phase == "combat":
        player = data["player"]
        for name, source in (("player.block", "block"), ("player.energy", "energy"), ("player.energy_per_turn", "energy_per_turn"), ("player.strength", "strength")):
            row[_G[name]] = _number(player[source], 1_000_000_000, name)
        row[_G["player.status_vulnerable"]] = _number(player["statuses"]["vulnerable"], 1_000_000_000, "player.status_vulnerable")
        row[_G["player.status_shrink"]] = _number(player["statuses"]["shrink"], 1_000_000_000, "player.status_shrink")
        for name, source in (("combat.turn", "turn"), ("combat.draw_pile_size", "draw_pile_size"), ("combat.discard_pile_size", "discard_pile_size"), ("combat.exhaust_pile_size", "exhaust_pile_size")):
            row[_G[name]] = _number(data[source], 1_000_000_000, name)
        row[_G["combat.terminal"]] = _boolean(data["terminal"], "combat.terminal")
        _one_hot(row, _G, "combat.outcome", data["outcome"], _REGISTRIES["combat_outcome"])
    else:
        row[_G["combat.outcome.none"]] = 1.0
    if phase == "reward": row[_G["reward.can_proceed"]] = _boolean(data["can_proceed"], "reward.can_proceed")
    if phase == "map":
        row[_G["map.has_current_node"]] = 0.0 if data["current_node_ref"] is None else 1.0
        row[_G["map.edge_count"]] = _number(len(data["edges"]), 128, "map.edge_count")
        row[_G["map.visited_node_count"]] = _number(len(data["visited_node_refs"]), 128, "map.visited_node_count")
    if phase == "room":
        row[_G["room.can_proceed"]] = _boolean(data["can_proceed"], "room.can_proceed")
        _one_hot(row, _G, "room.kind", data["room_kind"], _REGISTRIES["room_kind"])
    else: row[_G["room.kind.none"]] = 1.0
    if phase == "terminal": _one_hot(row, _G, "terminal.outcome", data["outcome"], _REGISTRIES["run_outcome"])
    else: row[_G["terminal.outcome.none"]] = 1.0
    if phase == "unsupported": _one_hot(row, _G, "unsupported.reason", data["reason_code"], _REGISTRIES["unsupported_reason"])
    else: row[_G["unsupported.reason.none"]] = 1.0
    return tuple(row)


def _events(events: Sequence[PublicEvent]) -> tuple[tuple[float, ...], ...]:
    result: list[tuple[float, ...]] = []
    for event in events:
        if type(event) is not PublicEvent: raise HeadlessEncodingError("public_events must contain exact PublicEvent values.")
        row = [0.0] * 78
        kind, data = event.event_type.value, event.data
        _one_hot(row, _V, "event_kind", kind, _REGISTRIES["public_event_kind"])
        _one_hot(row, _V, "event_phase", event.phase.value, _REGISTRIES["phase"])
        row[_V["sequence"]] = _number(event.sequence, 127, "event.sequence")
        if kind == "combat.card_played":
            row[_V["has_card_definition"]] = 1.0; _semantic(row, _V, "card_definition", data["card_definition_id"])
            if data["target_enemy_definition_id"] is not None:
                row[_V["has_target_enemy_definition"]] = 1.0; _semantic(row, _V, "target_enemy_definition", data["target_enemy_definition_id"])
        elif kind in ("combat.resolved", "run.terminated"):
            _one_hot(row, _V, "outcome", data["outcome"], _REGISTRIES["event_outcome"])
        elif kind in ("reward.gold_claimed", "room.rest_healed", "room.event_option_chosen"):
            row[_V["has_amount"]] = 1.0; row[_V["amount"]] = _number(data["amount"], 1_000_000_000, "event.amount")
            if kind == "room.event_option_chosen": _one_hot(row, _V, "effect", data["effect"], _REGISTRIES["room_effect_kind"])
        elif kind == "reward.card_opened":
            row[_V["has_offer_count"]] = 1.0; row[_V["offer_count"]] = _number(data["offer_count"], 128, "event.offer_count")
        elif kind == "reward.card_chosen":
            row[_V["has_card_definition"]] = 1.0; _semantic(row, _V, "card_definition", data["card_definition_id"])
            row[_V["has_upgraded"]] = 1.0; row[_V["upgraded"]] = _boolean(data["upgraded"], "event.upgraded")
        elif kind == "map.node_chosen": _one_hot(row, _V, "node_kind", data["node_kind"], _REGISTRIES["node_kind"])
        result.append(tuple(row))
    return tuple(result)


def encode_policy_view(view: PolicyView) -> EncodedPolicyView:
    """Encode one exact, validated public decision view."""
    if type(view) is not PolicyView: raise HeadlessEncodingError("view must be an exact PolicyView.")
    if CONTRACT_VERSION != "headless_v0" or CONTRACT_FINGERPRINT != _SOURCE_CONTRACT_FINGERPRINT:
        raise HeadlessEncodingError("headless_v0 fingerprint does not match the accepted encoding schema.")
    data, phase = view.observation.data, view.phase.value
    entity_rows: list[tuple[float, ...]] = []
    cards: dict[str, tuple[float, ...]] = {}; enemies: dict[str, tuple[float, ...]] = {}; rewards: dict[str, tuple[float, ...]] = {}; offers: dict[str, tuple[float, ...]] = {}; nodes: dict[str, tuple[float, ...]] = {}; options: dict[str, tuple[float, ...]] = {}
    def add(kind: str, item: Mapping[str, Any], ref: str, table: dict[str, tuple[float, ...]]) -> None:
        row = _entity(kind, item); entity_rows.append(row); table[ref] = row
    if phase == "combat":
        for item in data["enemies"]: add("enemy", item, item["enemy_ref"], enemies)
        for item in data["hand"]: add("card", item, item["card_ref"], cards)
    elif phase == "reward":
        for reward in data["rewards"]:
            add("reward", reward, reward["reward_ref"], rewards)
            for offer in reward["offers"]: add("offer", offer, offer["offer_ref"], offers)
    elif phase == "map":
        for item in data["nodes"]: add("node", item, item["node_ref"], nodes)
    elif phase == "room":
        for item in data["options"]: add("option", item, item["option_ref"], options)
    components: dict[str, dict[str, tuple[float, ...]]] = {"card": cards, "target_enemy": enemies, "reward": rewards, "offer": offers, "node": nodes, "option": options}
    candidate_rows: list[tuple[float, ...]] = []; candidate_ids: list[str] = []
    for candidate in view.candidates:
        try:
            if candidate_from_dict(candidate_to_dict(candidate)).candidate_id != candidate.candidate_id: raise ValueError
        except Exception as exc: raise HeadlessEncodingError("candidate ID is not canonical.") from exc
        candidate_id = candidate.candidate_id
        if not _CANDIDATE_ID.fullmatch(candidate_id) or candidate_id in candidate_ids: raise HeadlessEncodingError("candidate IDs must be unique canonical values.")
        row = [0.0] * 557; _one_hot(row, {name: i for i, name in enumerate(CANDIDATE_FEATURE_NAMES)}, "candidate_kind", candidate.kind.value, _REGISTRIES["candidate_kind"])
        joins: dict[str, str] = {}
        if candidate.kind is CandidateKind.COMBAT_PLAY_CARD:
            joins["card"] = candidate.card_ref
            if candidate.target_ref is not None: joins["target_enemy"] = candidate.target_ref
        elif candidate.kind in (CandidateKind.REWARD_CLAIM_GOLD, CandidateKind.REWARD_OPEN_CARD_REWARD, CandidateKind.REWARD_CHOOSE_CARD, CandidateKind.REWARD_SKIP_CARD):
            joins["reward"] = candidate.reward_ref
            if candidate.kind is CandidateKind.REWARD_CHOOSE_CARD: joins["offer"] = candidate.offer_ref
        elif candidate.kind is CandidateKind.MAP_CHOOSE_NODE: joins["node"] = candidate.node_ref
        elif candidate.kind in (CandidateKind.ROOM_REST_HEAL, CandidateKind.ROOM_EVENT_OPTION): joins["option"] = candidate.option_ref
        for offset, component in enumerate(("card", "target_enemy", "reward", "offer", "node", "option")):
            start = 11 + offset * 91
            if component in joins:
                try: source = components[component][joins[component]]
                except KeyError as exc: raise HeadlessEncodingError("candidate reference does not resolve in this view.") from exc
                row[start] = 1.0; row[start + 1:start + 91] = source
        candidate_rows.append(tuple(row)); candidate_ids.append(candidate_id)
    if view.status.value != "actionable" and (candidate_rows or candidate_ids): raise HeadlessEncodingError("non-actionable views cannot encode candidates.")
    encoded = EncodedPolicyView(ENCODING_VERSION, ENCODING_FINGERPRINT, _global(view), tuple(entity_rows), _events(view.public_events), tuple(candidate_rows), tuple(candidate_ids))
    _validate_encoded(encoded); return encoded


def _validate_rows(rows: Any, width: int, name: str) -> None:
    if type(rows) is not tuple: raise HeadlessEncodingError(f"{name} must be a tuple.")
    for row in rows:
        if type(row) is not tuple or len(row) != width: raise HeadlessEncodingError(f"{name} has an invalid row width.")
        for value in row:
            if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0: raise HeadlessEncodingError(f"{name} contains an invalid feature value.")


def _validate_encoded(record: EncodedPolicyView) -> None:
    if type(record) is not EncodedPolicyView: raise HeadlessEncodingError("record must be an exact EncodedPolicyView.")
    if record.encoding_version != ENCODING_VERSION or record.encoding_fingerprint != ENCODING_FINGERPRINT: raise HeadlessEncodingError("record schema identity does not match.")
    if type(record.global_features) is not tuple or len(record.global_features) != 47: raise HeadlessEncodingError("global row has an invalid width.")
    _validate_rows((record.global_features,), 47, "global_features"); _validate_rows(record.entity_rows, 90, "entity_rows"); _validate_rows(record.public_event_rows, 78, "public_event_rows"); _validate_rows(record.candidate_rows, 557, "candidate_rows")
    if type(record.candidate_ids) is not tuple or len(record.candidate_ids) != len(record.candidate_rows) or len(set(record.candidate_ids)) != len(record.candidate_ids) or any(type(value) is not str or not _CANDIDATE_ID.fullmatch(value) for value in record.candidate_ids): raise HeadlessEncodingError("candidate IDs do not align with candidate rows.")


def collate_policy_views(views: Sequence[EncodedPolicyView]) -> CollatedPolicyBatch:
    """Pad a sequence of encoded records with explicit boolean masks."""
    if not isinstance(views, Sequence) or isinstance(views, (str, bytes, bytearray)): raise HeadlessEncodingError("views must be a sequence of encoded records.")
    records = tuple(views)
    for record in records: _validate_encoded(record)
    batch_size = len(records); emax = max((len(item.entity_rows) for item in records), default=0); vmax = max((len(item.public_event_rows) for item in records), default=0); amax = max((len(item.candidate_rows) for item in records), default=0)
    global_features = np.zeros((batch_size, 47), dtype=np.float32); entity_features = np.zeros((batch_size, emax, 90), dtype=np.float32); event_features = np.zeros((batch_size, vmax, 78), dtype=np.float32); candidate_features = np.zeros((batch_size, amax, 557), dtype=np.float32)
    entity_mask = np.zeros((batch_size, emax), dtype=np.bool_); event_mask = np.zeros((batch_size, vmax), dtype=np.bool_); candidate_mask = np.zeros((batch_size, amax), dtype=np.bool_)
    for index, record in enumerate(records):
        global_features[index] = record.global_features
        if record.entity_rows: entity_features[index, :len(record.entity_rows)] = record.entity_rows; entity_mask[index, :len(record.entity_rows)] = True
        if record.public_event_rows: event_features[index, :len(record.public_event_rows)] = record.public_event_rows; event_mask[index, :len(record.public_event_rows)] = True
        if record.candidate_rows: candidate_features[index, :len(record.candidate_rows)] = record.candidate_rows; candidate_mask[index, :len(record.candidate_rows)] = True
    return CollatedPolicyBatch(ENCODING_VERSION, ENCODING_FINGERPRINT, global_features, entity_features, event_features, candidate_features, entity_mask, event_mask, candidate_mask, tuple(item.candidate_ids for item in records))
