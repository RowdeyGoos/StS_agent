"""Implemented reusable card operations, in authored execution order."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DealDamage:
    def apply(self, card, player, target) -> None:
        if target is None:
            raise ValueError("Damage requires a target.")
        damage = player.block if card.spec.damage_equals_player_block else card.spec.base_damage
        target.take_damage(damage, attacker_statuses=player.statuses, attacker_strength=player.strength)


@dataclass(frozen=True, slots=True)
class GainBlock:
    def apply(self, card, player, target) -> None:
        player.gain_block(card.spec.block_gain)


@dataclass(frozen=True, slots=True)
class DrawCards:
    def apply(self, card, player, target) -> None:
        player.draw_cards(card.spec.draw_count)


@dataclass(frozen=True, slots=True)
class ApplyTargetStatus:
    def apply(self, card, player, target) -> None:
        if target is None or card.spec.applies_status_name is None:
            raise ValueError("Status application requires its target and status rule.")
        target.apply_status(card.spec.applies_status_name, card.spec.applies_status_stacks)
