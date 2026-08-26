"""Versioned, exact card records for future learned RL representations.

This module is deliberately independent from :class:`CombatEnv` and the legacy
``ObservationEncoder``.  It converts the existing structured observation into
an opt-in record form without changing any environment or policy behavior.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any

from .actions import CombatAction, validate_action
from .card import CARD_SPECS, get_card_spec
from .encoding import DEFAULT_CARD_NAME_TO_ID, PAD_CARD_NAME
from .status import SHRINK, VULNERABLE

CARD_RECORD_FORMAT_VERSION = 1
CARD_ID_CAPACITY = 256
MAX_HAND_RECORDS = 10
MAX_DISTINCT_RECORDS_PER_PILE = 32
PILE_RECORD_ORDER: tuple[str, ...] = (
    "draw_pile",
    "discard_pile",
    "exhaust_pile",
)

# These categorical IDs are part of card-record format v1.  Extend them only by
# appending new IDs; changing an existing assignment requires a format bump.
CARD_KIND_TO_ID = MappingProxyType(
    {
        "<none>": 0,
        "attack": 1,
        "block": 2,
        "skill": 3,
        "status": 4,
    }
)
APPLIED_STATUS_NAME_TO_ID = MappingProxyType(
    {
        None: 0,
        SHRINK: 1,
        VULNERABLE: 2,
    }
)
DYNAMIC_DAMAGE_RULE_TO_ID = MappingProxyType(
    {
        "none": 0,
        "player_block": 1,
    }
)

CARD_SEMANTIC_FEATURE_NAMES: tuple[str, ...] = (
    "kind_is_attack",
    "kind_is_block",
    "kind_is_skill",
    "kind_is_status",
    "cost",
    "damage_per_hit",
    "hit_count",
    "block_gain",
    "draw_count",
    "applied_status_id",
    "applied_status_stacks",
    "dynamic_damage_rule_id",
    "exhausts",
    "uses_target",
)

CARD_NAME_TO_ID: Mapping[str, int] = MappingProxyType(dict(DEFAULT_CARD_NAME_TO_ID))
CARD_ID_TO_NAME: Mapping[int, str] = MappingProxyType(
    {card_id: name for name, card_id in CARD_NAME_TO_ID.items()}
)


@dataclass(frozen=True, slots=True)
class CardSemanticRecord:
    """Fixed-width static semantics for one append-only card ID."""

    card_id: int
    name: str
    kind_id: int
    cost: int
    damage_per_hit: int
    hit_count: int
    block_gain: int
    draw_count: int
    applied_status_id: int
    applied_status_stacks: int
    dynamic_damage_rule_id: int
    exhausts: bool
    uses_target: bool

    def feature_values(self) -> tuple[float, ...]:
        """Return the fixed numeric semantic row consumed by neural encoders."""
        return (
            1.0 if self.kind_id == CARD_KIND_TO_ID["attack"] else 0.0,
            1.0 if self.kind_id == CARD_KIND_TO_ID["block"] else 0.0,
            1.0 if self.kind_id == CARD_KIND_TO_ID["skill"] else 0.0,
            1.0 if self.kind_id == CARD_KIND_TO_ID["status"] else 0.0,
            float(self.cost),
            float(self.damage_per_hit),
            float(self.hit_count),
            float(self.block_gain),
            float(self.draw_count),
            float(self.applied_status_id),
            float(self.applied_status_stacks),
            float(self.dynamic_damage_rule_id),
            1.0 if self.exhausts else 0.0,
            1.0 if self.uses_target else 0.0,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PileCardRecord:
    """One exact observable ``(card ID, count)`` pile entry."""

    card_id: int
    count: int


@dataclass(frozen=True, slots=True)
class CardZoneRecords:
    """Ordered hand IDs plus canonical exact records for hidden card piles."""

    hand_card_ids: tuple[int, ...]
    draw_pile: tuple[PileCardRecord, ...]
    discard_pile: tuple[PileCardRecord, ...]
    exhaust_pile: tuple[PileCardRecord, ...]

    def pile(self, pile_name: str) -> tuple[PileCardRecord, ...]:
        """Return one pile by its stable format-v1 name."""
        if pile_name not in PILE_RECORD_ORDER:
            raise ValueError(f"Unsupported card-record pile: {pile_name!r}")
        return getattr(self, pile_name)


def validate_card_id_registry(
    mapping: Mapping[str, int] = CARD_NAME_TO_ID,
    *,
    expected_prefix: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Validate a gap-free append-only registry and return names in ID order."""
    if not mapping:
        raise ValueError("Card ID registry cannot be empty.")
    if mapping.get(PAD_CARD_NAME) != 0:
        raise ValueError(f"{PAD_CARD_NAME!r} must keep card ID 0.")

    ids = list(mapping.values())
    if any(not isinstance(card_id, int) or isinstance(card_id, bool) for card_id in ids):
        raise ValueError("Card IDs must be integers.")
    if len(ids) != len(set(ids)):
        raise ValueError("Card IDs must be unique.")
    if min(ids) < 0 or max(ids) >= CARD_ID_CAPACITY:
        raise ValueError(
            f"Card IDs must be in [0, {CARD_ID_CAPACITY})."
        )
    expected_ids = list(range(len(ids)))
    if sorted(ids) != expected_ids:
        raise ValueError("Card IDs must be contiguous and append-only from zero.")

    names_by_id = tuple(
        name
        for name, _card_id in sorted(mapping.items(), key=lambda item: item[1])
    )
    if expected_prefix is not None:
        prefix = tuple(expected_prefix)
        if names_by_id[: len(prefix)] != prefix:
            raise ValueError("Card ID registry does not preserve the required prefix.")
    return names_by_id


def get_card_id(card_name: str) -> int:
    """Return the stable append-only ID for a supported card name."""
    try:
        return CARD_NAME_TO_ID[card_name]
    except KeyError as exc:
        raise ValueError(f"Unknown card name for card records: {card_name!r}") from exc


def get_card_semantic_record(card_name_or_id: str | int) -> CardSemanticRecord:
    """Return fixed format-v1 semantics for a card name or ID."""
    if isinstance(card_name_or_id, bool):
        raise ValueError("Card IDs must be integers, not booleans.")
    if isinstance(card_name_or_id, int):
        try:
            card_name = CARD_ID_TO_NAME[card_name_or_id]
        except KeyError as exc:
            raise ValueError(
                f"Unknown card ID for card records: {card_name_or_id!r}"
            ) from exc
        card_id = card_name_or_id
    elif isinstance(card_name_or_id, str):
        card_name = card_name_or_id
        card_id = get_card_id(card_name)
    else:
        raise ValueError("Card semantic lookup requires a card name or integer ID.")

    if card_id == 0:
        return CardSemanticRecord(
            card_id=0,
            name=PAD_CARD_NAME,
            kind_id=0,
            cost=0,
            damage_per_hit=0,
            hit_count=0,
            block_gain=0,
            draw_count=0,
            applied_status_id=0,
            applied_status_stacks=0,
            dynamic_damage_rule_id=0,
            exhausts=False,
            uses_target=False,
        )

    spec = get_card_spec(card_name)
    try:
        kind_id = CARD_KIND_TO_ID[spec.kind]
    except KeyError as exc:
        raise ValueError(
            f"Card {card_name!r} has unsupported semantic kind {spec.kind!r}."
        ) from exc
    try:
        status_id = APPLIED_STATUS_NAME_TO_ID[spec.applies_status_name]
    except KeyError as exc:
        raise ValueError(
            f"Card {card_name!r} applies an unregistered status "
            f"{spec.applies_status_name!r}."
        ) from exc

    dynamic_rule = "player_block" if spec.damage_equals_player_block else "none"
    has_damage = spec.base_damage > 0 or spec.damage_equals_player_block
    hit_count = int(getattr(spec, "attack_count", 1 if has_damage else 0))
    return CardSemanticRecord(
        card_id=card_id,
        name=card_name,
        kind_id=kind_id,
        cost=spec.cost,
        damage_per_hit=spec.base_damage,
        hit_count=hit_count,
        block_gain=spec.block_gain,
        draw_count=spec.draw_count,
        applied_status_id=status_id,
        applied_status_stacks=spec.applies_status_stacks,
        dynamic_damage_rule_id=DYNAMIC_DAMAGE_RULE_TO_ID[dynamic_rule],
        exhausts=spec.exhausts,
        uses_target=spec.uses_target,
    )


def extract_card_zone_records(observation: Mapping[str, Any]) -> CardZoneRecords:
    """Extract exact observable hand and pile composition from an observation."""
    hand = observation.get("hand")
    if not isinstance(hand, list):
        raise ValueError("Observation field 'hand' must be a list.")
    if len(hand) > MAX_HAND_RECORDS:
        raise ValueError(
            f"Hand size {len(hand)} exceeds MAX_HAND_RECORDS={MAX_HAND_RECORDS}."
        )
    hand_names = tuple(_require_card_name(value, "hand") for value in hand)
    hand_card_ids = tuple(get_card_id(name) for name in hand_names)

    card_counts = observation.get("card_counts")
    if not isinstance(card_counts, Mapping):
        raise ValueError("Observation field 'card_counts' must be a mapping.")

    hand_counts = _extract_count_mapping(card_counts, "hand")
    if hand_counts != Counter(hand_names):
        raise ValueError(
            "Observation card_counts['hand'] does not match the ordered hand."
        )

    pile_records: dict[str, tuple[PileCardRecord, ...]] = {}
    for pile_name in PILE_RECORD_ORDER:
        counts = _extract_count_mapping(card_counts, pile_name)
        records = tuple(
            PileCardRecord(card_id=get_card_id(name), count=count)
            for name, count in sorted(
                counts.items(),
                key=lambda item: get_card_id(item[0]),
            )
        )
        if len(records) > MAX_DISTINCT_RECORDS_PER_PILE:
            raise ValueError(
                f"Pile {pile_name!r} has {len(records)} distinct cards, exceeding "
                f"MAX_DISTINCT_RECORDS_PER_PILE={MAX_DISTINCT_RECORDS_PER_PILE}."
            )
        size_key = f"{pile_name}_size"
        observed_size = _require_nonnegative_int(observation.get(size_key), size_key)
        actual_size = sum(record.count for record in records)
        if observed_size != actual_size:
            raise ValueError(
                f"Observation field {size_key!r} is {observed_size}, but exact "
                f"card counts total {actual_size}."
            )
        pile_records[pile_name] = records

    records = CardZoneRecords(
        hand_card_ids=hand_card_ids,
        draw_pile=pile_records["draw_pile"],
        discard_pile=pile_records["discard_pile"],
        exhaust_pile=pile_records["exhaust_pile"],
    )
    validate_card_zone_records(records)
    return records


def validate_card_zone_records(records: CardZoneRecords) -> None:
    """Validate capacities, known IDs, exact counts, and canonical pile order."""
    if len(records.hand_card_ids) > MAX_HAND_RECORDS:
        raise ValueError(
            f"Hand has more than MAX_HAND_RECORDS={MAX_HAND_RECORDS} records."
        )
    for card_id in records.hand_card_ids:
        _require_known_non_pad_card_id(card_id, "hand")

    for pile_name in PILE_RECORD_ORDER:
        pile = records.pile(pile_name)
        if len(pile) > MAX_DISTINCT_RECORDS_PER_PILE:
            raise ValueError(
                f"Pile {pile_name!r} exceeds its distinct-record capacity."
            )
        previous_id = 0
        for record in pile:
            _require_known_non_pad_card_id(record.card_id, pile_name)
            if record.card_id <= previous_id:
                raise ValueError(
                    f"Pile {pile_name!r} records must have unique, strictly "
                    "ascending card IDs."
                )
            _require_positive_int(record.count, f"{pile_name} count")
            previous_id = record.card_id


def get_action_card_id(
    observation: Mapping[str, Any],
    action: CombatAction,
) -> int:
    """Return the played card ID, or padding ID zero for ``end_turn``."""
    validate_action(action)
    if action[0] == "end_turn":
        return 0

    hand = observation.get("hand")
    if not isinstance(hand, list):
        raise ValueError("Observation field 'hand' must be a list.")
    hand_index = action[1]
    if hand_index < 0 or hand_index >= len(hand):
        raise ValueError(
            f"Hand index {hand_index} is out of range for action card lookup."
        )
    return get_card_id(_require_card_name(hand[hand_index], "hand"))


def card_semantic_feature_table() -> tuple[tuple[float, ...], ...]:
    """Return a fixed-capacity semantic lookup table indexed by card ID."""
    zero_row = (0.0,) * len(CARD_SEMANTIC_FEATURE_NAMES)
    rows = [zero_row for _ in range(CARD_ID_CAPACITY)]
    for card_id in sorted(CARD_ID_TO_NAME):
        rows[card_id] = get_card_semantic_record(card_id).feature_values()
    return tuple(rows)


def card_record_schema_dict() -> dict[str, Any]:
    """Return the complete deterministic format-v1 schema and current catalog."""
    names_by_id = validate_card_id_registry()
    registered_card_names = set(names_by_id) - {PAD_CARD_NAME}
    if registered_card_names != set(CARD_SPECS):
        missing_specs = sorted(registered_card_names - set(CARD_SPECS))
        missing_ids = sorted(set(CARD_SPECS) - registered_card_names)
        raise ValueError(
            "Card ID registry and CARD_SPECS differ: "
            f"missing_specs={missing_specs}, missing_ids={missing_ids}."
        )
    return {
        "format": "card_records",
        "version": CARD_RECORD_FORMAT_VERSION,
        "card_id_capacity": CARD_ID_CAPACITY,
        "max_hand_records": MAX_HAND_RECORDS,
        "max_distinct_records_per_pile": MAX_DISTINCT_RECORDS_PER_PILE,
        "pile_record_order": list(PILE_RECORD_ORDER),
        "semantic_feature_names": list(CARD_SEMANTIC_FEATURE_NAMES),
        "card_kind_ids": dict(CARD_KIND_TO_ID),
        "applied_status_ids": {
            "<none>" if name is None else name: status_id
            for name, status_id in APPLIED_STATUS_NAME_TO_ID.items()
        },
        "dynamic_damage_rule_ids": dict(DYNAMIC_DAMAGE_RULE_TO_ID),
        "cards": [
            get_card_semantic_record(card_id).as_dict()
            for card_id in range(len(names_by_id))
        ],
    }


def card_record_schema_fingerprint() -> str:
    """Return the lowercase SHA-256 digest of the canonical schema JSON."""
    canonical_json = json.dumps(
        card_record_schema_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return sha256(canonical_json.encode("utf-8")).hexdigest()


def _extract_count_mapping(
    card_counts: Mapping[str, Any],
    pile_name: str,
) -> Counter[str]:
    raw_counts = card_counts.get(pile_name)
    if not isinstance(raw_counts, Mapping):
        raise ValueError(
            f"Observation card_counts[{pile_name!r}] must be a mapping."
        )
    counts: Counter[str] = Counter()
    for raw_name, raw_count in raw_counts.items():
        name = _require_card_name(raw_name, f"card_counts[{pile_name!r}]")
        count = _require_nonnegative_int(
            raw_count,
            f"card_counts[{pile_name!r}][{name!r}]",
        )
        get_card_id(name)
        if count > 0:
            counts[name] = count
    return counts


def _require_card_name(value: Any, location: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Card name in {location} must be a string.")
    return value


def _require_nonnegative_int(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{location} must be a non-negative integer.")
    return value


def _require_positive_int(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{location} must be a positive integer.")
    return value


def _require_known_non_pad_card_id(card_id: Any, location: str) -> int:
    if not isinstance(card_id, int) or isinstance(card_id, bool):
        raise ValueError(f"Card ID in {location} must be an integer.")
    if card_id == 0:
        raise ValueError(f"Padding card ID 0 cannot be an active {location} record.")
    if card_id not in CARD_ID_TO_NAME:
        raise ValueError(f"Unknown card ID {card_id!r} in {location}.")
    return card_id


_CURRENT_CARD_ID_PREFIX = (
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
validate_card_id_registry(expected_prefix=_CURRENT_CARD_ID_PREFIX)
