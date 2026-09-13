"""Combat execution with no observation, encoder, reward or transport dependency."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Callable, Sequence

from game.headless.cards.base import Card
from game.headless.cards.ironclad import create_starter_deck
from game.headless.core.actions import CombatAction, EndTurn, PlayCard
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.core.utils import make_rng
from game.headless.monsters.base import EncounterFactory, Enemy
from game.headless.monsters.overgrowth import SimpleEnemy


@dataclass(frozen=True, slots=True)
class CombatResult:
    done: bool
    winner: str | None
    details: dict


class CombatEngine:
    """Own mutable combat state and execute legal game commands.

    The existing rules are a partial simulator. This architectural extraction
    does not change or certify the native damage/turn/RNG semantics.
    """

    def __init__(
        self, *, seed: int = 0,
        deck_factory: Callable[[], Sequence[Card]] = create_starter_deck,
        enemy_factory: Callable[[], Enemy] | None = None,
        encounter_factory: EncounterFactory | None = None,
        player_max_hp: int = 80, energy_per_turn: int = 3, cards_per_turn: int = 5,
    ) -> None:
        if type(seed) is not int:
            raise ValueError("Combat seed must be an explicit integer.")
        if type(player_max_hp) is not int or player_max_hp <= 0:
            raise ValueError("Player maximum HP must be positive.")
        if any(type(value) is not int or value < 0 for value in (energy_per_turn, cards_per_turn)):
            raise ValueError("Turn energy and draw count must be nonnegative integers.")
        self.rng = make_rng(seed)
        self.deck_factory = deck_factory
        self.enemy_factory = enemy_factory or SimpleEnemy
        self.encounter_factory = encounter_factory
        self.player_max_hp = player_max_hp
        self.energy_per_turn = energy_per_turn
        self.cards_per_turn = cards_per_turn
        self.player: Player | None = None
        self.enemies: list[Enemy] | None = None
        self.turn = 0
        self.done = False
        self.winner: str | None = None

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            if type(seed) is not int:
                raise ValueError("Combat seed must be an integer.")
            self.rng = make_rng(seed)
        self.player = self._build_player()
        self.enemies = self._build_encounter()
        self.player.combat_enemies = self.enemies
        self.turn = 1
        self.done = False
        self.winner = None
        self.player.start_turn(draw_count=self.cards_per_turn)
        self._refresh_persistent_statuses()

    def legal_actions(self) -> tuple[CombatAction, ...]:
        self._ensure_ready()
        if self.done:
            return ()
        actions: list[CombatAction] = [EndTurn()]
        for card in self.player.hand:
            if card.cost > self.player.energy:
                continue
            if card.spec.uses_target:
                actions.extend(PlayCard(card.instance_id, slot) for slot in self._living_enemy_indices())
            else:
                actions.append(PlayCard(card.instance_id))
        return tuple(actions)

    def apply(self, action: CombatAction) -> CombatResult:
        self._ensure_ready()
        if self.done:
            raise RuntimeError("Combat is already finished. Call reset() to start a new run.")
        if action not in self.legal_actions():
            raise ValueError(f"Illegal action for current state: {action!r}")
        details = {}
        if isinstance(action, PlayCard):
            hand_index = next(i for i, card in enumerate(self.player.hand) if card.instance_id == action.instance_id)
            target = None if action.target_slot is None else self.enemies[action.target_slot]
            card = self.player.play_card(hand_index, target)
            details = {"played_card": card.name, "target_enemy_index": action.target_slot,
                       "target_enemy_name": None if target is None else target.name}
            self._refresh_persistent_statuses()
            self._check_terminal()
            return CombatResult(self.done, self.winner, details)

        self.player.end_turn()
        enemy_actions = []
        for slot, enemy in enumerate(self.enemies):
            if not enemy.is_alive:
                continue
            enemy.start_turn()
            executed = enemy.execute_intent(self.player)
            enemy_actions.append({"enemy_index": slot, "enemy_name": enemy.name, "intent": executed.as_dict()})
            self._refresh_persistent_statuses()
            self._check_terminal()
            if self.done:
                break
        details["enemy_actions"] = enemy_actions
        if len(enemy_actions) == 1:
            details["enemy_action"] = enemy_actions[0]["intent"]
        if not self.done:
            self.turn += 1
            self.player.start_turn(draw_count=self.cards_per_turn)
            self._refresh_persistent_statuses()
        return CombatResult(self.done, self.winner, details)

    def snapshot(self, *, cards=None, monsters=None) -> dict:
        from game.headless.core.snapshots import capture_combat
        return capture_combat(self, cards=cards, monsters=monsters)

    def resolve_external_effect(self) -> CombatResult:
        """Settle an already validated item effect before run-level handoff."""
        self._ensure_ready()
        self._refresh_persistent_statuses()
        self._check_terminal()
        return CombatResult(self.done, self.winner, {})

    def restore(self, snapshot: dict, *, cards=None, monsters=None) -> None:
        from game.headless.core.snapshots import restore_combat
        # Decoder constructs and validates a separate graph before installation.
        restored = restore_combat(snapshot, cards=cards, monsters=monsters)
        for name, value in restored.items():
            setattr(self, name, value)

    def _build_player(self) -> Player:
        return Player(Deck(deepcopy(self.deck_factory()), rng=self.rng), self.player_max_hp, self.energy_per_turn)

    def _build_encounter(self) -> list[Enemy]:
        result = list(self.encounter_factory(self.rng)) if self.encounter_factory else [self.enemy_factory()]
        if not result:
            raise ValueError("Encounter factory must create at least one enemy.")
        return result

    def _living_enemies(self) -> list[Enemy]:
        return [enemy for enemy in self.enemies if enemy.is_alive]

    def _living_enemy_indices(self) -> list[int]:
        return [i for i, enemy in enumerate(self.enemies) if enemy.is_alive]

    def _check_terminal(self) -> None:
        if not self._living_enemies():
            self.done, self.winner = True, "player"
        elif not self.player.is_alive:
            self.done, self.winner = True, "enemy"

    def _refresh_persistent_statuses(self) -> None:
        # Existing reduced Shrink rule; broader source-owned powers remain content work.
        if not any(e.is_alive and e.name == "Shrinker Beetle" for e in self.enemies):
            stacks = self.player.statuses.get("shrink")
            if stacks:
                self.player.statuses.decrement("shrink", stacks)

    def _ensure_ready(self) -> None:
        if self.player is None or self.enemies is None:
            raise RuntimeError("Combat engine is not initialized. Call reset() before use.")
