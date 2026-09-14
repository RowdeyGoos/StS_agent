"""Combat execution with no observation, encoder, reward or transport dependency."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Callable, Sequence

from game.headless.cards.base import Card
from game.headless.cards.ironclad import create_starter_deck
from game.headless.core.actions import CombatAction, ChooseCombatCard, ConfirmCombatSelection, EndTurn, PlayCard
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.powers.lifecycle import after_owner_side_turn_end
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
        player_max_hp: int = 80, energy_per_turn: int = 3, cards_per_turn: int = 5, cards=None,
    ) -> None:
        if type(seed) is not int:
            raise ValueError("Combat seed must be an explicit integer.")
        if type(player_max_hp) is not int or player_max_hp <= 0:
            raise ValueError("Player maximum HP must be positive.")
        if any(type(value) is not int or value < 0 for value in (energy_per_turn, cards_per_turn)):
            raise ValueError("Turn energy and draw count must be nonnegative integers.")
        self.card_catalog = cards
        self.rng = make_rng(seed)
        self.native_streams = None
        self.encounter_rng = None
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

    def reset(self, seed: int | None = None, *, relics=(), initial_hp=None, room_kind="combat", potion_capacity=3, potion_slots=3, potions=(), potion_pool=None, gold=0) -> None:
        if seed is not None:
            if type(seed) is not int:
                raise ValueError("Combat seed must be an integer.")
            self.rng = make_rng(seed)
        self.player = self._build_player()
        self.player.catalog = self.card_catalog
        self.enemies = self._build_encounter()
        self.player.combat_enemies = self.enemies
        for enemy in self.enemies:
            enemy.combat_player = self.player
        self.turn = 1
        self.done = False
        self.winner = None
        from dataclasses import asdict
        self.player.rules.gold_available = gold
        self.player.rules.potions = [None if item is None else asdict(item) for item in potions]
        if potion_pool is not None:
            self.player.rules.potion_pool = list(potion_pool)
        from game.headless.relics.combat import install
        install(self.player, relics, room_kind=room_kind, hp=initial_hp, potion_capacity=potion_capacity, potion_slots=potion_slots)
        self.player.start_turn(draw_count=self.cards_per_turn)
        self._refresh_persistent_statuses()
        self._check_terminal()

    def legal_actions(self) -> tuple[CombatAction, ...]:
        self._ensure_ready()
        if self.done:
            return ()
        if self.player.rules.selection is not None:
            from game.headless.core.choices import actions
            return actions(self.player)
        if self.player.pending_play is not None:
            return tuple(ChooseCombatCard(i) for i in self.player.pending_options())
        actions: list[CombatAction] = [EndTurn()]
        from game.headless.cards.curses import can_play
        for card in self.player.hand:
            if not can_play(self.player, card):
                continue
            if self.player.statuses.get("ringing") and self.player.cards_played_this_turn:
                continue
            if (card.cost < 0 and not card.spec.x_cost) or self.player.card_cost(card) > self.player.energy:
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
        if isinstance(action, (ChooseCombatCard, ConfirmCombatSelection)):
            if self.player.rules.selection is not None:
                from game.headless.core.choices import confirm, toggle
                confirm(self.player) if isinstance(action, ConfirmCombatSelection) else toggle(self.player, action.instance_id)
            else:
                self.player.choose_combat_card(action.instance_id)
            self._refresh_persistent_statuses()
            self._check_terminal()
            if self.player.rules.enemy_turn is not None and not self.done and self.player.pending_play is None and self.player.rules.selection is None:
                return self._continue_enemy_side()
            if self.player.rules.turn_ending and self.player.pending_play is None and self.player.rules.selection is None and not self.done:
                return self._finish_turn()
            return CombatResult(self.done, self.winner, {"selected_card": getattr(action, "instance_id", None)})
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
        self._check_terminal()
        if self.player.pending_play is not None or self.player.rules.selection is not None or self.done:
            return CombatResult(self.done, self.winner, {"enemy_actions": []})
        return self._finish_turn()

    def _finish_turn(self):
        details = {}
        after_owner_side_turn_end(self.player)
        self.player.rules.player_side = False
        self.player.rules.turn_ending = False
        self._refresh_persistent_statuses()
        self._check_terminal()
        if self.done:
            return CombatResult(self.done, self.winner, {"enemy_actions": []})
        self.player.rules.enemy_turn = {'limit': len(self.enemies), 'slot': 0, 'move': None, 'actions': []}
        return self._continue_enemy_side()

    def _continue_enemy_side(self):
        from game.headless.core.enemy_turn import begin, execute, paused
        progress = self.player.rules.enemy_turn
        enemy_actions = progress['actions']
        details = {}
        while progress['slot'] < progress['limit']:
            slot = progress['slot']
            enemy = self.enemies[slot]
            if progress['move'] is None:
                if not enemy.can_take_turn:
                    progress['slot'] += 1
                    continue
                enemy.start_turn()
                progress['move'] = begin(enemy)
            execute(enemy, self.player, progress['move'])
            self._refresh_persistent_statuses()
            self._check_terminal()
            if paused(self.player) and not self.done:
                return CombatResult(False, None, {'enemy_actions': list(enemy_actions)})
            from game.headless.monsters.base import Intent
            executed = Intent(**progress['move']['intent'])
            enemy_actions.append({'enemy_index': slot, 'enemy_name': enemy.name, 'intent': executed.as_dict()})
            progress['slot'] += 1
            progress['move'] = None
            if self.done:
                break
        self.player.rules.enemy_turn = None
        details["enemy_actions"] = enemy_actions
        if len(enemy_actions) == 1:
            details["enemy_action"] = enemy_actions[0]["intent"]
        if not self.done:
            # Weak/Vulnerable tick once after the whole enemy side, on both sides.
            self.player.statuses.after_enemy_side_turn_end()
            for enemy in self._living_enemies():
                enemy.statuses.after_enemy_side_turn_end()
                after_owner_side_turn_end(enemy)
            from game.headless.powers.ironclad import after_enemy_end
            after_enemy_end(self.player)
            self.turn += 1
            self.player.start_turn(draw_count=self.cards_per_turn)
            self._refresh_persistent_statuses()
            self._check_terminal()
        return CombatResult(self.done, self.winner, details)

    def snapshot(self, *, cards=None, monsters=None) -> dict:
        from game.headless.core.snapshots import capture_combat
        return capture_combat(self, cards=cards or self.player.catalog, monsters=monsters)

    def resolve_external_effect(self) -> CombatResult:
        """Settle an already validated item effect before run-level handoff."""
        self._ensure_ready()
        from game.headless.core.resolution import drain
        drain(self.player)
        self._refresh_persistent_statuses()
        self._check_terminal()
        return CombatResult(self.done, self.winner, {"enemy_actions": []})

    def restore(self, snapshot: dict, *, cards=None, monsters=None) -> None:
        from game.headless.core.snapshots import restore_combat
        # Decoder constructs and validates a separate graph before installation.
        restored = restore_combat(snapshot, cards=cards or self.card_catalog, monsters=monsters)
        for name, value in restored.items():
            setattr(self, name, value)

    def _build_player(self) -> Player:
        return Player(Deck(deepcopy(self.deck_factory()), rng=self.native_streams["shuffle"] if self.native_streams else self.rng, streams=self.native_streams), self.player_max_hp, self.energy_per_turn)

    def _build_encounter(self) -> list[Enemy]:
        result = list(self.encounter_factory(self.encounter_rng or self.rng)) if self.encounter_factory else [self.enemy_factory()]
        if not result:
            raise ValueError("Encounter factory must create at least one enemy.")
        return result

    def _living_enemies(self) -> list[Enemy]:
        return [enemy for enemy in self.enemies if enemy.is_alive]

    def _living_enemy_indices(self) -> list[int]:
        return [i for i, enemy in enumerate(self.enemies) if enemy.is_alive]

    def _check_terminal(self) -> None:
        if not self._living_enemies() and self.player.combat_is_ending:
            self.done, self.winner = True, "player"
        elif not self.player.is_alive:
            self.done, self.winner = True, "enemy"

    def _refresh_persistent_statuses(self) -> None:
        from game.headless.core.enemy_lifecycle import settle_enemies
        settle_enemies(self.player)

    def _ensure_ready(self) -> None:
        if self.player is None or self.enemies is None:
            raise RuntimeError("Combat engine is not initialized. Call reset() before use.")
