"""Fixed-width observation and action encoding utilities for RL agents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .action_features import (
    _action_summary_cache_key,
    _prepare_action_summary_context,
    action_feature_names,
    encode_action_summary_features,
    infer_legal_actions_from_observation,
    summarize_action,
)
from .actions import CombatAction, validate_action
from .status import STATUS_STACK_SCALE, SUPPORTED_STATUS_NAMES

PAD_CARD_NAME = "<PAD>"
DEFAULT_CARD_NAME_TO_ID: dict[str, int] = {
    PAD_CARD_NAME: 0,
    "Strike": 1,
    "Defend": 2,
    "Bash": 3,
    "Slimed": 4,
    "Pommel Strike": 5,
    "Shrug It Off": 6,
    "Iron Wave": 7,
    "Body Slam": 8,
}
DEFAULT_ENEMY_NAME_TO_ID: dict[str, int] = {
    "SimpleEnemy": 1,
    "Nibbit": 2,
    "Leaf Slime (S)": 3,
    "Leaf Slime (M)": 4,
    "Twig Slime (S)": 5,
    "Twig Slime (M)": 6,
    "Shrinker Beetle": 7,
    "Fuzzy Wurm Crawler": 8,
}
DEFAULT_MOVE_NAME_TO_ID: dict[str, int] = {
    "Strike": 1,
    "Defend": 2,
    "Heavy Strike": 3,
    "Butt": 4,
    "Hesitant Slice": 5,
    "Hiss": 6,
    "Shrinker": 7,
    "Chomp": 8,
    "Stomp": 9,
    "Acid Goop": 10,
    "Inhale": 11,
    "Tackle": 12,
    "Goop": 13,
    "Sticky Shot": 14,
    "Clump Shot": 15,
}
PILE_COUNT_ORDER: tuple[str, ...] = ("hand", "draw_pile", "discard_pile", "exhaust_pile")
BEHAVIOR_STATE_SCALE = 8.0


@dataclass(slots=True)
class ObservationEncoder:
    """Encode dict observations and tuple actions into fixed RL-friendly formats."""

    max_hand_size: int = 10
    max_enemy_count: int = 1
    card_name_to_id: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_CARD_NAME_TO_ID)
    )
    enemy_name_to_id: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_ENEMY_NAME_TO_ID)
    )
    move_name_to_id: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_MOVE_NAME_TO_ID)
    )
    _supported_card_names: tuple[str, ...] = field(init=False, repr=False)
    _supported_enemy_names: tuple[str, ...] = field(init=False, repr=False)
    _supported_move_names: tuple[str, ...] = field(init=False, repr=False)
    _action_feature_names: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_hand_size <= 0:
            raise ValueError("max_hand_size must be positive.")
        if self.max_enemy_count <= 0:
            raise ValueError("max_enemy_count must be positive.")
        if self.card_name_to_id.get(PAD_CARD_NAME) != 0:
            raise ValueError(f"{PAD_CARD_NAME!r} must be mapped to id 0.")
        self._supported_card_names = tuple(
            card_name
            for card_name, card_id in sorted(
                self.card_name_to_id.items(),
                key=lambda item: item[1],
            )
            if card_name != PAD_CARD_NAME
        )
        self._supported_enemy_names = tuple(
            enemy_name
            for enemy_name, _enemy_id in sorted(
                self.enemy_name_to_id.items(),
                key=lambda item: item[1],
            )
        )
        self._supported_move_names = tuple(
            move_name
            for move_name, _move_id in sorted(
                self.move_name_to_id.items(),
                key=lambda item: item[1],
            )
        )
        self._action_feature_names = action_feature_names(
            supported_card_names=self._supported_card_names,
            supported_enemy_names=self._supported_enemy_names,
            supported_status_names=self.supported_status_names,
        )

    @property
    def action_space_size(self) -> int:
        """Return the size of the fixed discrete action space."""
        return 1 + (self.max_hand_size * self.max_enemy_count)

    @property
    def supported_card_names(self) -> tuple[str, ...]:
        """Return all card names that can be encoded, excluding the pad token."""
        return self._supported_card_names

    @property
    def supported_enemy_names(self) -> tuple[str, ...]:
        """Return all enemy names that can be encoded."""
        return self._supported_enemy_names

    @property
    def supported_status_names(self) -> tuple[str, ...]:
        """Return all status names that can appear in encoded observations."""
        return SUPPORTED_STATUS_NAMES

    @property
    def supported_move_names(self) -> tuple[str, ...]:
        """Return all move names that can be encoded in behavior-state features."""
        return self._supported_move_names

    @property
    def scalar_feature_names(self) -> tuple[str, ...]:
        """Return the names of scalar features in the encoded vector."""
        player_status_feature_names = tuple(
            f"player_status_{status_name}_fraction"
            for status_name in self.supported_status_names
        )
        return (
            "player_hp_fraction",
            "player_max_hp_scale",
            "player_block_scale",
            "player_energy_fraction",
            "player_strength_scale",
            *player_status_feature_names,
            "draw_pile_fraction",
            "discard_pile_fraction",
            "exhaust_pile_fraction",
            "hand_size_fraction",
            "living_enemy_fraction",
            "turn_progress",
        )

    @property
    def scalar_feature_count(self) -> int:
        """Return the number of normalized scalar features."""
        return len(self.scalar_feature_names)

    @property
    def pile_count_feature_count(self) -> int:
        """Return the number of aggregate pile-composition features."""
        return len(PILE_COUNT_ORDER) * len(self.supported_card_names)

    @property
    def enemy_slot_feature_names(self) -> tuple[str, ...]:
        """Return the names of per-enemy-slot features."""
        enemy_type_feature_names = tuple(
            f"name_is_{enemy_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            for enemy_name in self.supported_enemy_names
        )
        status_feature_names = tuple(
            f"status_{status_name}_fraction"
            for status_name in self.supported_status_names
        )
        intent_status_feature_names = tuple(
            f"intent_status_{status_name}_fraction"
            for status_name in self.supported_status_names
        )
        behavior_next_move_feature_names = tuple(
            f"behavior_next_move_can_be_{move_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            for move_name in self.supported_move_names
        )
        return (
            "alive",
            "hp_fraction",
            "max_hp_scale",
            "block_scale",
            "strength_scale",
            *status_feature_names,
            "intent_attack_fraction",
            "intent_block_fraction",
            "intent_strength_gain_fraction",
            *intent_status_feature_names,
            "intent_slimed_fraction",
            "behavior_phase_fraction",
            "behavior_phase_count_fraction",
            "behavior_next_move_count_fraction",
            *behavior_next_move_feature_names,
            *enemy_type_feature_names,
        )

    @property
    def enemy_slot_feature_count(self) -> int:
        """Return the number of features per enemy slot."""
        return len(self.enemy_slot_feature_names)

    @property
    def total_enemy_slot_feature_count(self) -> int:
        """Return the total number of encoded enemy-slot features."""
        return self.max_enemy_count * self.enemy_slot_feature_count

    @property
    def slot_feature_count(self) -> int:
        """Return the number of one-hot hand-slot features."""
        return self.max_hand_size * len(self.supported_card_names)

    @property
    def base_feature_count(self) -> int:
        """Return the number of non-hand features in the encoded vector."""
        return (
            self.scalar_feature_count
            + self.pile_count_feature_count
            + self.total_enemy_slot_feature_count
        )

    @property
    def vector_size(self) -> int:
        """Return the full encoded observation length."""
        return self.base_feature_count + self.slot_feature_count

    @property
    def action_feature_names(self) -> tuple[str, ...]:
        """Return semantic names for each encoded action feature."""
        return self._action_feature_names

    @property
    def action_feature_count(self) -> int:
        """Return the width of one encoded legal-action feature vector."""
        return len(self.action_feature_names)

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Return the semantic name of every feature in the encoded vector."""
        pile_count_feature_names = tuple(
            f"{pile_name}_count_{card_name.lower().replace(' ', '_')}_fraction"
            for pile_name in PILE_COUNT_ORDER
            for card_name in self.supported_card_names
        )
        enemy_slot_feature_names = tuple(
            f"enemy_{slot_index}_{feature_name}"
            for slot_index in range(self.max_enemy_count)
            for feature_name in self.enemy_slot_feature_names
        )
        hand_slot_feature_names = tuple(
            f"hand_slot_{slot_index}_is_{card_name.lower().replace(' ', '_')}"
            for slot_index in range(self.max_hand_size)
            for card_name in self.supported_card_names
        )
        return (
            *self.scalar_feature_names,
            *pile_count_feature_names,
            *enemy_slot_feature_names,
            *hand_slot_feature_names,
        )

    def encode(self, observation: Mapping[str, Any]) -> tuple[float, ...]:
        """Convert a structured observation dict into a fixed-length float vector."""
        player = _require_mapping(observation, "player")
        card_counts = _require_mapping(observation, "card_counts")
        player_statuses = _require_mapping(player, "statuses")
        enemies = _get_enemies(observation)

        hand = observation.get("hand")
        if not isinstance(hand, list):
            raise ValueError("Observation field 'hand' must be a list.")
        if len(hand) > self.max_hand_size:
            raise ValueError(
                f"Hand size {len(hand)} exceeds encoder max_hand_size={self.max_hand_size}."
            )
        if len(enemies) > self.max_enemy_count:
            raise ValueError(
                f"Enemy count {len(enemies)} exceeds encoder max_enemy_count={self.max_enemy_count}."
            )

        supported_card_names = self.supported_card_names
        supported_card_name_set = set(supported_card_names)
        supported_enemy_names = self.supported_enemy_names
        supported_enemy_name_set = set(supported_enemy_names)
        supported_move_names = self.supported_move_names
        supported_move_name_set = set(supported_move_names)

        for card_name in hand:
            self._validate_card_name(str(card_name), supported_card_name_set)

        total_cards = max(
            1,
            len(hand)
            + int(observation["draw_pile_size"])
            + int(observation["discard_pile_size"])
            + int(observation["exhaust_pile_size"]),
        )
        living_enemy_count = sum(1 for enemy in enemies if bool(enemy.get("alive", True)))
        hp_scale = max(
            int(player["max_hp"]),
            max((int(enemy["max_hp"]) for enemy in enemies), default=1),
            1,
        )
        energy_per_turn = max(1, int(player.get("energy_per_turn", player["energy"])))

        encoded_vector = [
            float(player["hp"]) / max(1.0, float(player["max_hp"])),
            float(player["max_hp"]) / float(hp_scale),
            float(player["block"]) / float(hp_scale),
            float(player["energy"]) / float(energy_per_turn),
            float(int(player.get("strength", 0))) / float(hp_scale),
            *self._encode_status_features(player_statuses),
            float(observation["draw_pile_size"]) / float(total_cards),
            float(observation["discard_pile_size"]) / float(total_cards),
            float(observation["exhaust_pile_size"]) / float(total_cards),
            float(len(hand)) / float(self.max_hand_size),
            float(living_enemy_count) / float(self.max_enemy_count),
            float(observation["turn"]) / (float(observation["turn"]) + float(total_cards)),
            *self._encode_pile_count_features(
                card_counts=card_counts,
                supported_card_names=supported_card_names,
                total_cards=total_cards,
            ),
            *self._encode_enemy_slots(
                enemies=enemies,
                supported_enemy_names=supported_enemy_names,
                supported_enemy_name_set=supported_enemy_name_set,
                supported_move_names=supported_move_names,
                supported_move_name_set=supported_move_name_set,
                hp_scale=hp_scale,
            ),
            *self._encode_hand_slots(hand, supported_card_names),
        ]
        return tuple(encoded_vector)

    def _encode_status_features(self, statuses: Mapping[str, Any]) -> list[float]:
        """Encode supported status stacks as normalized scalar features."""
        return [
            float(int(statuses.get(status_name, 0))) / STATUS_STACK_SCALE
            for status_name in self.supported_status_names
        ]

    def _encode_pile_count_features(
        self,
        card_counts: Mapping[str, Any],
        supported_card_names: tuple[str, ...],
        total_cards: int,
    ) -> list[float]:
        """Encode per-pile card counts as normalized aggregate features."""
        supported_card_name_set = set(supported_card_names)
        encoded_features: list[float] = []
        for pile_name in PILE_COUNT_ORDER:
            pile_counts = _require_mapping(card_counts, pile_name)
            for card_name in pile_counts:
                self._validate_card_name(str(card_name), supported_card_name_set)
            for card_name in supported_card_names:
                encoded_features.append(
                    float(int(pile_counts.get(card_name, 0))) / float(total_cards)
                )
        return encoded_features

    def _encode_enemy_slots(
        self,
        enemies: list[Mapping[str, Any]],
        supported_enemy_names: tuple[str, ...],
        supported_enemy_name_set: set[str],
        supported_move_names: tuple[str, ...],
        supported_move_name_set: set[str],
        hp_scale: int,
    ) -> list[float]:
        """Encode a fixed number of enemy slots."""
        encoded_slots: list[float] = []
        for slot_index in range(self.max_enemy_count):
            enemy = enemies[slot_index] if slot_index < len(enemies) else None
            encoded_slots.extend(
                self._encode_enemy_slot(
                    enemy=enemy,
                    supported_enemy_names=supported_enemy_names,
                    supported_enemy_name_set=supported_enemy_name_set,
                    supported_move_names=supported_move_names,
                    supported_move_name_set=supported_move_name_set,
                    hp_scale=hp_scale,
                )
            )
        return encoded_slots

    def _encode_enemy_slot(
        self,
        enemy: Mapping[str, Any] | None,
        supported_enemy_names: tuple[str, ...],
        supported_enemy_name_set: set[str],
        supported_move_names: tuple[str, ...],
        supported_move_name_set: set[str],
        hp_scale: int,
    ) -> list[float]:
        """Encode one enemy slot."""
        if enemy is None:
            return [0.0] * self.enemy_slot_feature_count

        enemy_statuses = _require_mapping(enemy, "statuses")
        intent = _require_mapping(enemy, "intent")
        behavior_state = _require_mapping(enemy, "behavior_state")
        enemy_name = str(enemy["name"])
        self._validate_enemy_name(enemy_name, supported_enemy_name_set)

        possible_next_move_names = behavior_state.get("possible_next_move_names", [])
        if not isinstance(possible_next_move_names, list):
            raise ValueError(
                "Enemy behavior_state field 'possible_next_move_names' must be a list."
            )
        for move_name in possible_next_move_names:
            self._validate_move_name(str(move_name), supported_move_name_set)

        intent_status_features = []
        for status_name in self.supported_status_names:
            if str(intent.get("status_name")) == status_name:
                intent_status_features.append(
                    float(int(intent.get("status_stacks", 0))) / STATUS_STACK_SCALE
                )
            else:
                intent_status_features.append(0.0)

        next_move_features = [
            1.0 if supported_move_name in possible_next_move_names else 0.0
            for supported_move_name in supported_move_names
        ]
        enemy_type_features = [
            1.0 if enemy_name == supported_enemy_name else 0.0
            for supported_enemy_name in supported_enemy_names
        ]

        phase_count = max(1, int(behavior_state.get("phase_count", 1)))
        phase_index = max(0, int(behavior_state.get("phase_index", 0)))

        return [
            1.0 if bool(enemy.get("alive", True)) else 0.0,
            float(enemy["hp"]) / max(1.0, float(enemy["max_hp"])),
            float(enemy["max_hp"]) / float(hp_scale),
            float(enemy["block"]) / float(hp_scale),
            float(int(enemy.get("strength", 0))) / float(hp_scale),
            *self._encode_status_features(enemy_statuses),
            float(int(intent.get("attack_damage", 0))) / float(hp_scale),
            float(int(intent.get("block_gain", 0))) / float(hp_scale),
            float(int(intent.get("strength_gain", 0))) / float(hp_scale),
            *intent_status_features,
            float(int(intent.get("slimed_added", 0))) / float(self.max_hand_size),
            float(phase_index) / BEHAVIOR_STATE_SCALE,
            float(phase_count) / BEHAVIOR_STATE_SCALE,
            float(len(possible_next_move_names)) / float(len(supported_move_names)),
            *next_move_features,
            *enemy_type_features,
        ]

    def _encode_hand_slots(
        self,
        hand: list[Any],
        supported_card_names: tuple[str, ...],
    ) -> list[float]:
        """Encode every hand slot as a one-hot card indicator."""
        encoded_slots: list[float] = []
        for slot_index in range(self.max_hand_size):
            slot_card_name = str(hand[slot_index]) if slot_index < len(hand) else None
            for card_name in supported_card_names:
                encoded_slots.append(1.0 if slot_card_name == card_name else 0.0)
        return encoded_slots

    def _validate_card_name(
        self,
        card_name: str,
        supported_card_name_set: set[str] | None = None,
    ) -> None:
        """Raise if an observation contains a card the encoder does not know about."""
        known_card_names = supported_card_name_set or set(self.supported_card_names)
        if card_name not in known_card_names:
            raise ValueError(f"Unknown card name for encoding: {card_name!r}")

    def _validate_enemy_name(
        self,
        enemy_name: str,
        supported_enemy_name_set: set[str] | None = None,
    ) -> None:
        """Raise if an observation contains an enemy the encoder does not know about."""
        known_enemy_names = supported_enemy_name_set or set(self.supported_enemy_names)
        if enemy_name not in known_enemy_names:
            raise ValueError(f"Unknown enemy name for encoding: {enemy_name!r}")

    def _validate_move_name(
        self,
        move_name: str,
        supported_move_name_set: set[str] | None = None,
    ) -> None:
        """Raise if an observation contains a move the encoder does not know about."""
        known_move_names = supported_move_name_set or set(self.supported_move_names)
        if move_name not in known_move_names:
            raise ValueError(f"Unknown move name for encoding: {move_name!r}")

    def encode_legal_actions(
        self, legal_actions: list[CombatAction] | tuple[CombatAction, ...]
    ) -> tuple[int, ...]:
        """Convert legal tuple actions into a fixed-size binary action mask."""
        mask = [0] * self.action_space_size
        for action in legal_actions:
            mask[self.encode_action(action)] = 1
        return tuple(mask)

    def encode_action(self, action: CombatAction) -> int:
        """Map a tuple action into the discrete action space."""
        validate_action(action)

        if action[0] == "end_turn":
            return 0

        hand_index = action[1]
        if hand_index < 0 or hand_index >= self.max_hand_size:
            raise ValueError(
                f"Hand index {hand_index} is outside the discrete action space."
            )
        target_index = 0 if len(action) == 2 else action[2]
        if target_index < 0 or target_index >= self.max_enemy_count:
            raise ValueError(
                f"Enemy index {target_index} is outside the discrete action space."
            )
        return 1 + (hand_index * self.max_enemy_count) + target_index

    def decode_action(self, action_index: int) -> CombatAction:
        """Map a discrete action index back into the tuple action API."""
        if action_index < 0 or action_index >= self.action_space_size:
            raise ValueError(
                f"Action index {action_index} is outside [0, {self.action_space_size})."
            )
        if action_index == 0:
            return ("end_turn",)

        encoded_play_index = action_index - 1
        hand_index = encoded_play_index // self.max_enemy_count
        target_index = encoded_play_index % self.max_enemy_count
        if self.max_enemy_count == 1:
            return ("play", hand_index)
        return ("play", hand_index, target_index)

    def encode_action_features(
        self,
        observation: Mapping[str, Any],
        legal_actions: list[CombatAction] | tuple[CombatAction, ...] | None = None,
    ) -> tuple[tuple[float, ...], ...]:
        """Encode every discrete action slot as a fixed action-feature vector."""
        source_legal_actions = (
            tuple(legal_actions)
            if legal_actions is not None
            else infer_legal_actions_from_observation(observation)
        )
        player = _require_mapping(observation, "player")
        enemies = _get_enemies(observation)
        hp_scale = max(
            int(player["max_hp"]),
            max((int(enemy["max_hp"]) for enemy in enemies), default=1),
            1,
        )
        energy_per_turn = max(1, int(player.get("energy_per_turn", player["energy"])))
        supported_card_names = self.supported_card_names
        supported_enemy_names = self.supported_enemy_names
        supported_status_names = self.supported_status_names
        action_feature_count = self.action_feature_count
        summary_context = _prepare_action_summary_context(observation)
        semantic_feature_cache: dict[
            tuple[str, str | None, int | None], tuple[float, ...]
        ] = {}

        encoded_features = [
            [0.0] * action_feature_count for _ in range(self.action_space_size)
        ]
        for action in source_legal_actions:
            cache_key = _action_summary_cache_key(summary_context, action)
            action_features = semantic_feature_cache.get(cache_key)
            if action_features is None:
                action_summary = summarize_action(
                    observation,
                    action,
                    context=summary_context,
                )
                action_features = encode_action_summary_features(
                    action_summary,
                    supported_card_names=supported_card_names,
                    supported_enemy_names=supported_enemy_names,
                    supported_status_names=supported_status_names,
                    max_enemy_count=self.max_enemy_count,
                    max_hand_size=self.max_hand_size,
                    hp_scale=hp_scale,
                    energy_per_turn=energy_per_turn,
                )
                semantic_feature_cache[cache_key] = action_features
            encoded_features[self.encode_action(action)] = action_features

        return tuple(tuple(row) for row in encoded_features)


def _require_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Observation field {key!r} must be a mapping.")
    return value


def _get_enemies(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    enemies = observation.get("enemies")
    if isinstance(enemies, list):
        return [
            enemy
            for enemy in enemies
            if isinstance(enemy, Mapping)
        ]

    enemy = observation.get("enemy")
    if isinstance(enemy, Mapping):
        return [enemy]

    raise ValueError("Observation must contain 'enemies' or 'enemy'.")
