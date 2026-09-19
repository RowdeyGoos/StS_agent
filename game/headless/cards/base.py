"""Card definitions are immutable rules; card instances carry mutable game state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from game.headless.core.selection import HandChoice

if TYPE_CHECKING:
    from game.headless.core.player import Player
    from game.headless.monsters.base import Enemy


@dataclass(frozen=True, slots=True)
class CardSpec:
    """Resolved values for one upgrade level, shared by execution and inspection."""

    name: str
    cost: int
    kind: str
    base_damage: int = 0
    block_gain: int = 0
    draw_count: int = 0
    damage_equals_player_block: bool = False
    applies_status_name: str | None = None
    applies_status_stacks: int = 0
    exhausts: bool = False
    uses_target: bool = True
    ethereal: bool = False
    end_turn_damage: int = 0
    end_turn_hp_loss: int = 0
    innate: bool = False
    x_cost: bool = False
    retain: bool = False
    eternal: bool = False
    sly: bool = False
    star_cost: int = -1
    star_x: bool = False

    @property
    def is_dead_card(self) -> bool:
        return (
            self.base_damage <= 0 and self.block_gain <= 0 and self.draw_count <= 0
            and not self.damage_equals_player_block and self.applies_status_name is None
            and self.applies_status_stacks <= 0
        )


class CardEffect(Protocol):
    """One rule operation. Complex cards can supply their own immutable effect."""

    def apply(self, card: Card, player: Player, target: Enemy | None) -> HandChoice | None: ...


@dataclass(frozen=True, slots=True)
class CardDefinition:
    definition_id: str
    levels: tuple[CardSpec, ...]
    effects: tuple[CardEffect, ...]
    combat_lifetime: int = 0
    rarity: str = "special"
    pool: str = "special"
    strike: bool = False
    defend: bool = False
    generate_in_combat: bool = True

    def __post_init__(self) -> None:
        if not self.definition_id or not self.levels:
            raise ValueError("A card definition needs an ID and at least its base level.")
        object.__setattr__(self, "levels", tuple(self.levels))
        object.__setattr__(self, "effects", tuple(self.effects))

    def spec_at(self, upgrade_level: int) -> CardSpec:
        if type(upgrade_level) is not int or not 0 <= upgrade_level < len(self.levels):
            raise ValueError(f"Unsupported upgrade level for {self.definition_id}: {upgrade_level!r}.")
        return self.levels[upgrade_level]

    def __deepcopy__(self, memo):
        # Immutable authored content is shared; instances and their state are not.
        return self


class Card:
    """An exact card instance; display names never determine its game behavior."""

    def __init__(
        self, definition: CardDefinition | str, cost: int | None = None,
        exhausts: bool = False, *, upgrade_level: int = 0, instance_id: str | None = None,
    ) -> None:
        # Retain the old custom-card constructor at the compatibility seam.
        if isinstance(definition, str):
            if cost is None:
                raise ValueError("A custom card requires a cost.")
            definition = CardDefinition(
                definition, (CardSpec(definition, cost, "skill", exhausts=exhausts),), ()
            )
        definition.spec_at(upgrade_level)
        self.definition = definition
        self.upgrade_level = upgrade_level
        self.instance_id = instance_id
        self.combats_seen = 0
        self.permanent_damage = 0
        self.permanent_block = 0
        self.enchantment = None
        from game.headless.core.card_state import CardState
        self.combat_state = CardState()

    @property
    def spec(self) -> CardSpec:
        spec = self.definition.spec_at(self.upgrade_level)
        if self.enchantment is not None and self.enchantment.definition_id == "royally_approved":
            from dataclasses import replace
            spec = replace(spec, innate=True, retain=True)
        if self.enchantment is not None:
            from dataclasses import replace
            if self.enchantment.definition_id == 'goopy':
                spec = replace(spec, exhausts=True)
            elif self.enchantment.definition_id == 'tezcataras_ember':
                spec = replace(spec, cost=0, eternal=True)
        if self.permanent_damage:
            from dataclasses import replace
            spec = replace(spec, base_damage=spec.base_damage + self.permanent_damage)
        if self.permanent_block:
            from dataclasses import replace
            spec = replace(spec, block_gain=spec.block_gain + self.permanent_block)
        state = self.combat_state
        if state.retain_this_turn or state.retain_this_combat or state.sly_this_turn or state.sly_this_combat or state.all_enemies or state.ethereal_this_combat:
            from dataclasses import replace
            spec = replace(spec, retain=spec.retain or state.retain_this_turn or state.retain_this_combat,
                           sly=spec.sly or state.sly_this_turn or state.sly_this_combat,
                           uses_target=spec.uses_target and not state.all_enemies,
                           ethereal=spec.ethereal or state.ethereal_this_combat)
        return spec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def cost(self) -> int:
        return self.spec.cost

    @property
    def exhausts(self) -> bool:
        return self.spec.exhausts

    @property
    def upgraded(self) -> bool:
        return self.upgrade_level > 0

    def preview_upgrade(self) -> CardSpec:
        return self.definition.spec_at(self.upgrade_level + 1)

    def upgrade(self) -> None:
        self.preview_upgrade()
        self.upgrade_level += 1

    def play(self, player: Player, enemy: Enemy | None, *, start_effect: int = 0):
        """Compatibility entry for an isolated effect play without energy payment.

        Game callers use Player/CombatEngine so ownership, legality and suspended
        choices remain explicit. The old effect-index restart is no longer needed.
        """
        from game.headless.core.resolution import start_play, drain, move_out
        if start_effect or player.pending_play is not None:
            raise ValueError("Resume choices through Player.choose_combat_card().")
        origin = next(((pile, pile.index(self)) for pile in
                       (player.deck.hand, player.deck.draw_pile, player.deck.discard_pile,
                        player.deck.exhaust_pile) if self in pile), None)
        prior_enemies = player.combat_enemies
        try:
            start_play(player, self, enemy, auto=True)
            drain(player)
            if player.pending_play is not None:
                # A suspended choice must retain its target slots until resolved.
                return player.pending_play.effect_index, HandChoice(player.pending_options())
            # This legacy helper applies effects; its caller retains pile authority.
            move_out(player, self)
            if origin is not None:
                origin[0].insert(origin[1], self)
            return None
        finally:
            if player.pending_play is None:
                player.combat_enemies = prior_enemies

    def __repr__(self) -> str:
        return f"{self.name}(cost={self.cost}, exhausts={self.exhausts})"
