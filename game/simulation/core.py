"""Main single-combat environment with an RL-friendly interface."""

from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any, Callable, Sequence

from .actions import CombatAction, validate_action
from .card import Card, create_starter_deck, get_card_spec
from .deck import Deck
from .encoding import ObservationEncoder
from game.headless.core.combat import CombatEngine
from game.headless.core.actions import PlayCard, EndTurn
from .enemy import EncounterFactory, Enemy, SimpleEnemy
from .player import Player
from .status import modify_attack_damage_for_statuses
from .trajectory import EpisodeSummary, TransitionRecord
from .utils import apply_damage_to_block_and_hp, make_rng

Observation = dict[str, Any]


class CombatEnv(CombatEngine):
    """Single-player combat environment with RL-friendly observations and actions.

    Rewards use simple shaping:
    - `+1` on victory
    - `-1` on defeat
    - minus scaled player HP loss during the step
    - plus a small bonus for reducing projected incoming enemy damage during the player turn
    """

    def __init__(
        self,
        seed: int | None = None,
        deck_factory: Callable[[], Sequence[Card]] = create_starter_deck,
        enemy_factory: Callable[[], Enemy] | None = None,
        encounter_factory: EncounterFactory | None = None,
        player_max_hp: int = 80,
        energy_per_turn: int = 3,
        cards_per_turn: int = 5,
        max_hand_size: int = 10,
        max_enemy_count: int = 1,
        hp_loss_penalty_scale: float = 1.0,
        incoming_damage_shaping_scale: float = 0.5,
        record_trajectory: bool = True,
    ) -> None:
        super().__init__(
            seed=0 if seed is None else seed, deck_factory=deck_factory,
            enemy_factory=enemy_factory, encounter_factory=encounter_factory,
            player_max_hp=player_max_hp, energy_per_turn=energy_per_turn,
            cards_per_turn=cards_per_turn,
        )
        if seed is None:
            self.rng = make_rng()  # Preserve the legacy unseeded constructor API.
        self.hp_loss_penalty_scale = hp_loss_penalty_scale
        self.incoming_damage_shaping_scale = incoming_damage_shaping_scale
        self.record_trajectory = record_trajectory
        self.encoder = ObservationEncoder(
            max_hand_size=max_hand_size,
            max_enemy_count=max_enemy_count,
        )

        self.last_observation: Observation | None = None
        self.episode_reward = 0.0
        self.episode_step_count = 0
        self.episode_transitions: list[TransitionRecord] = []

    @property
    def enemy(self) -> Enemy | None:
        """Compatibility alias for single-enemy callers."""
        if not self.enemies:
            return None
        living_enemies = self._living_enemies()
        if living_enemies:
            return living_enemies[0]
        return self.enemies[0]

    def reset(self, seed: int | None = None) -> Observation:
        """Reset combat and return the initial observation."""
        CombatEngine.reset(self, seed)
        self.episode_reward = 0.0
        self.episode_step_count = 0
        self.episode_transitions = []
        self.last_observation = self.get_observation()
        return self.last_observation

    def step(self, action: CombatAction) -> tuple[Observation, float, bool, dict[str, Any]]:
        """Advance the environment by applying a legal player action."""
        self._ensure_ready()
        if self.done:
            raise RuntimeError("Combat is already finished. Call reset() to start a new run.")

        validate_action(action)
        if action not in self.get_legal_actions():
            raise ValueError(f"Illegal action for current state: {action!r}")

        assert self.player is not None
        assert self.enemies is not None
        assert self.last_observation is not None

        previous_observation = self.last_observation
        if action[0] == "play":
            target_slot = self._resolve_target_index(action)
            card = self.player.hand[action[1]]
            command = PlayCard(card.instance_id, target_slot if card.spec.uses_target else None)
        else:
            command = EndTurn()
        result = CombatEngine.apply(self, command)
        info = dict(result.details)
        if action[0] == "play":
            # Legacy diagnostics give even untargeted cards a canonical enemy slot.
            info["target_enemy_index"] = target_slot
            info["target_enemy_name"] = self.enemies[target_slot].name
        reward = (1.0 if self.winner == "player" else -1.0) if self.done else 0.0
        return self._finalize_step(
            action=action, previous_observation=previous_observation,
            next_observation=self.get_observation(), reward=reward, info=info,
        )

    def step_discrete(self, action_index: int) -> tuple[Observation, float, bool, dict[str, Any]]:
        """Advance the environment using the fixed discrete action encoding."""
        action = self.decode_action(action_index)
        return self.step(action)

    def get_legal_actions(self) -> list[CombatAction]:
        """Return all legal actions for the current player decision point."""
        self._ensure_ready()
        if self.done:
            return []

        assert self.player is not None

        actions: list[CombatAction] = []
        living = self._living_enemy_indices()
        for command in self.legal_actions():
            if isinstance(command, EndTurn):
                actions.append(("end_turn",))
                continue
            index = next(i for i, card in enumerate(self.player.hand) if card.instance_id == command.instance_id)
            if self.encoder.max_enemy_count == 1 and len(living) == 1:
                actions.append(("play", index))
            else:
                target = command.target_slot if command.target_slot is not None else living[0]
                actions.append(("play", index, target))
        return actions

    def get_action_mask(self) -> tuple[int, ...]:
        """Return a fixed-size legal-action mask for discrete RL agents."""
        return self.encoder.encode_legal_actions(self.get_legal_actions())

    def encode_policy_inputs(
        self,
        observation: Observation | None = None,
    ) -> tuple[tuple[int, ...], tuple[tuple[float, ...], ...]]:
        """Encode the action mask and features from one shared legality result."""
        source_observation = (
            observation if observation is not None else self.get_observation()
        )
        legal_actions = self.get_legal_actions()
        return (
            self.encoder.encode_legal_actions(legal_actions),
            self.encoder.encode_action_features(
                source_observation,
                legal_actions=legal_actions,
            ),
        )

    def get_observation(self) -> Observation:
        """Return a structured observation of the current combat state."""
        self._ensure_ready()
        assert self.player is not None
        assert self.enemies is not None
        card_counts = self._get_card_counts()
        enemy_observations = [enemy.to_observation() for enemy in self.enemies]

        observation: Observation = {
            "turn": self.turn,
            "player": {
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "block": self.player.block,
                "energy": self.player.energy,
                "energy_per_turn": self.player.energy_per_turn,
                "strength": self.player.strength,
                "statuses": self.player.statuses.as_dict(),
            },
            "enemies": enemy_observations,
            "enemy_count": len(enemy_observations),
            "living_enemy_count": len(self._living_enemies()),
            "hand": [card.name for card in self.player.hand],
            "draw_pile_size": len(self.player.deck.draw_pile),
            "discard_pile_size": len(self.player.deck.discard_pile),
            "exhaust_pile_size": len(self.player.deck.exhaust_pile),
            "card_counts": card_counts,
        }
        if enemy_observations:
            observation["enemy"] = enemy_observations[0]
        return observation

    def encode_observation(self, observation: Observation | None = None) -> tuple[float, ...]:
        """Return a fixed-width numeric encoding of an observation."""
        source_observation = observation if observation is not None else self.get_observation()
        return self.encoder.encode(source_observation)

    def encode_action_features(
        self,
        observation: Observation | None = None,
        *,
        action_mask: Sequence[int] | None = None,
    ) -> tuple[tuple[float, ...], ...]:
        """Return fixed action-conditioned features for every discrete action slot."""
        source_observation = observation if observation is not None else self.get_observation()
        if action_mask is not None:
            if len(action_mask) != self.action_space_size:
                raise ValueError(
                    "Action mask length does not match the discrete action space."
                )
            legal_actions = tuple(
                self.decode_action(action_index)
                for action_index, is_legal in enumerate(action_mask)
                if is_legal
            )
        else:
            legal_actions = self.get_legal_actions() if observation is None else None
        return self.encoder.encode_action_features(
            source_observation,
            legal_actions=legal_actions,
        )

    def encode_action(self, action: CombatAction) -> int:
        """Encode a tuple action into the fixed discrete action space."""
        return self.encoder.encode_action(action)

    def decode_action(self, action_index: int) -> CombatAction:
        """Decode a discrete action index into the tuple action API."""
        return self.encoder.decode_action(action_index)

    @property
    def action_space_size(self) -> int:
        """Return the size of the discrete action space used for RL."""
        return self.encoder.action_space_size

    @property
    def observation_size(self) -> int:
        """Return the length of the encoded observation vector."""
        return self.encoder.vector_size

    @property
    def action_feature_size(self) -> int:
        """Return the width of one encoded action-feature vector."""
        return self.encoder.action_feature_count

    def get_episode_history(self) -> tuple[TransitionRecord, ...]:
        """Return the transitions recorded in the current episode."""
        return tuple(self.episode_transitions)

    def get_episode_summary(self) -> EpisodeSummary:
        """Return aggregate episode statistics for the current run."""
        self._ensure_ready()
        assert self.player is not None

        return EpisodeSummary(
            total_reward=self.episode_reward,
            steps=self.episode_step_count,
            final_turn=self.turn,
            winner=self.winner,
            player_hp=self.player.hp,
            enemy_hp=sum(enemy.hp for enemy in self._living_enemies()),
        )

    def _build_encounter(self) -> list[Enemy]:
        encounter = super()._build_encounter()
        if len(encounter) > self.encoder.max_enemy_count:
            raise ValueError(
                f"Encounter has {len(encounter)} enemies, exceeding max_enemy_count="
                f"{self.encoder.max_enemy_count}."
            )
        return encounter

    def _get_card_counts(self) -> dict[str, dict[str, int]]:
        """Return per-pile card-name counts for richer observation encoding."""
        assert self.player is not None
        return {
            "hand": self._count_cards_by_name(self.player.hand),
            "draw_pile": self._count_cards_by_name(self.player.deck.draw_pile),
            "discard_pile": self._count_cards_by_name(self.player.deck.discard_pile),
            "exhaust_pile": self._count_cards_by_name(self.player.deck.exhaust_pile),
        }

    def _count_cards_by_name(self, cards: Sequence[Card]) -> dict[str, int]:
        """Count cards by name for observation serialization."""
        counts = Counter(card.name for card in cards)
        return dict(sorted(counts.items()))

    def _living_enemies(self) -> list[Enemy]:
        assert self.enemies is not None
        return [enemy for enemy in self.enemies if enemy.is_alive]

    def _living_enemy_indices(self) -> list[int]:
        assert self.enemies is not None
        return [index for index, enemy in enumerate(self.enemies) if enemy.is_alive]

    def _resolve_target_index(self, action: CombatAction) -> int:
        """Resolve a play action into the targeted enemy slot."""
        living_enemy_indices = self._living_enemy_indices()
        if not living_enemy_indices:
            raise RuntimeError("No living enemies remain to target.")

        if len(action) == 3:
            target_index = action[2]
            if target_index not in living_enemy_indices:
                raise ValueError(f"Target enemy index {target_index} is not a legal target.")
            return target_index

        if len(living_enemy_indices) == 1:
            return living_enemy_indices[0]

        raise ValueError("Multi-enemy encounters require explicit target indices.")

    def _finalize_step(
        self,
        action: CombatAction,
        previous_observation: Observation,
        next_observation: Observation,
        reward: float,
        info: dict[str, Any],
    ) -> tuple[Observation, float, bool, dict[str, Any]]:
        self.last_observation = next_observation
        hp_loss_penalty, player_hp_lost = self._calculate_hp_loss_penalty(
            previous_observation=previous_observation,
            next_observation=next_observation,
        )
        incoming_damage_bonus, projected_before, projected_after = (
            self._calculate_incoming_damage_reduction_bonus(
                action=action,
                previous_observation=previous_observation,
                next_observation=next_observation,
            )
        )
        scaled_hp_loss_penalty = self.hp_loss_penalty_scale * hp_loss_penalty
        shaped_reward = reward + scaled_hp_loss_penalty + incoming_damage_bonus
        self.episode_reward += shaped_reward
        step_index = self.episode_step_count
        self.episode_step_count += 1

        if self.record_trajectory:
            transition = TransitionRecord(
                step_index=step_index,
                turn=int(previous_observation["turn"]),
                action=action,
                action_index=self.encode_action(action),
                reward=shaped_reward,
                done=self.done,
                observation=previous_observation,
                next_observation=next_observation,
                info=dict(info),
            )
            self.episode_transitions.append(transition)

        enriched_info = dict(info)
        enriched_info["player_hp_lost"] = player_hp_lost
        enriched_info["hp_loss_penalty"] = scaled_hp_loss_penalty
        enriched_info["raw_hp_loss_penalty"] = hp_loss_penalty
        enriched_info["projected_incoming_hp_loss_before"] = projected_before
        enriched_info["projected_incoming_hp_loss_after"] = projected_after
        enriched_info["incoming_damage_reduction_bonus"] = incoming_damage_bonus
        enriched_info["action_mask"] = self.get_action_mask()
        if self.done:
            enriched_info["episode_summary"] = self.get_episode_summary().as_dict()

        return next_observation, shaped_reward, self.done, enriched_info

    def _calculate_hp_loss_penalty(
        self,
        previous_observation: Observation,
        next_observation: Observation,
    ) -> tuple[float, int]:
        previous_player = previous_observation["player"]
        next_player = next_observation["player"]
        assert isinstance(previous_player, dict)
        assert isinstance(next_player, dict)

        previous_hp = int(previous_player["hp"])
        next_hp = int(next_player["hp"])
        max_hp = int(previous_player["max_hp"])
        player_hp_lost = max(0, previous_hp - next_hp)
        hp_loss_penalty = -(player_hp_lost / max_hp) if player_hp_lost > 0 else 0.0
        return hp_loss_penalty, player_hp_lost

    def _calculate_incoming_damage_reduction_bonus(
        self,
        action: CombatAction,
        previous_observation: Observation,
        next_observation: Observation,
    ) -> tuple[float, int, int]:
        """Reward player actions that reduce immediate projected incoming HP loss."""
        projected_before = self._project_incoming_hp_loss(previous_observation)
        projected_after = self._project_incoming_hp_loss(next_observation)

        if (
            self.incoming_damage_shaping_scale <= 0.0
            or action[0] != "play"
            or self.done
        ):
            return 0.0, projected_before, projected_after

        previous_player = previous_observation["player"]
        assert isinstance(previous_player, dict)
        max_hp = max(1, int(previous_player["max_hp"]))
        damage_reduction_fraction = (projected_before - projected_after) / max_hp
        bonus = self.incoming_damage_shaping_scale * damage_reduction_fraction
        return bonus, projected_before, projected_after

    def _project_incoming_hp_loss(self, observation: Observation) -> int:
        """Estimate HP loss from currently telegraphed enemy attacks in slot order."""
        player = observation["player"]
        enemies = observation.get("enemies", [observation["enemy"]])
        assert isinstance(player, dict)
        assert isinstance(enemies, list)

        player_statuses = player["statuses"]
        assert isinstance(player_statuses, dict)

        original_hp = int(player["hp"])
        simulated_hp = int(player["hp"])
        simulated_block = int(player["block"])
        for enemy in enemies:
            if not isinstance(enemy, dict) or not bool(enemy.get("alive", True)):
                continue
            intent = enemy["intent"]
            if not isinstance(intent, dict):
                continue
            base_attack_damage = int(intent.get("attack_damage", 0))
            attack_count = int(intent.get("attack_count", 1 if base_attack_damage > 0 else 0))
            if base_attack_damage <= 0 or attack_count <= 0:
                continue

            for _hit_index in range(attack_count):
                resolved_attack_damage = modify_attack_damage_for_statuses(
                    base_attack_damage,
                    player_statuses,
                )
                simulated_hp, simulated_block = apply_damage_to_block_and_hp(
                    simulated_hp,
                    simulated_block,
                    resolved_attack_damage,
                )
                if simulated_hp <= 0:
                    return original_hp

        return max(0, original_hp - simulated_hp)
