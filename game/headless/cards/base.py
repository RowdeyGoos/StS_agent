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
        self, definition: CardDefinition, *,
        upgrade_level: int = 0, instance_id: str | None = None,
    ) -> None:
        definition.spec_at(upgrade_level)
        self.definition = definition
        self.upgrade_level = upgrade_level
        self.instance_id = instance_id
        self.combats_seen = 0
        self.permanent_damage = 0
        self.permanent_block = 0
        self.enchantment = None
        self.event_data = {"kind": "attack", "rider": "sapping"} if definition.definition_id == "mad_science" else {}
        from game.headless.core.card_state import CardState
        self.combat_state = CardState()

    @property
    def spec(self) -> CardSpec:
        spec = self.definition.spec_at(self.upgrade_level)
        if self.definition.definition_id == "mad_science":
            from dataclasses import replace
            kind = self.event_data["kind"]
            spec = replace(spec, kind=kind, uses_target=kind == "attack", base_damage=12 if kind == "attack" else 0, block_gain=8 if kind == "skill" else 0)
        if self.enchantment is not None and self.enchantment.definition_id == "royally_approved":
            from dataclasses import replace
            spec = replace(spec, innate=True, retain=True)
        if self.enchantment is not None:
            from dataclasses import replace
            if self.enchantment.definition_id == 'goopy':
                spec = replace(spec, exhausts=True)
            elif self.enchantment.definition_id == 'steady':
                spec = replace(spec, retain=True)
            elif self.enchantment.definition_id == 'souls_power':
                spec = replace(spec, exhausts=False)
            elif self.enchantment.definition_id == 'tezcataras_ember':
                spec = replace(spec, cost=0, eternal=True)
        if self.permanent_damage:
            from dataclasses import replace
            spec = replace(spec, base_damage=spec.base_damage + self.permanent_damage)
        if self.permanent_block:
            from dataclasses import replace
            spec = replace(spec, block_gain=spec.block_gain + self.permanent_block)
        state = self.combat_state
        if state.wither_level:
            from dataclasses import replace
            spec = replace(spec, name=f"Wither+{state.wither_level}", end_turn_damage=3 + 3 * state.wither_level)
        if state.hexed:
            from dataclasses import replace
            spec = replace(spec, ethereal=True)
        if state.is_dupe:
            from dataclasses import replace
            spec = replace(spec, exhausts=False)
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

    def __repr__(self) -> str:
        return f"{self.name}(cost={self.cost}, exhausts={self.exhausts})"
