"""Card definitions are immutable rules; card instances carry mutable game state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

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

    @property
    def is_dead_card(self) -> bool:
        return (
            self.base_damage <= 0 and self.block_gain <= 0 and self.draw_count <= 0
            and not self.damage_equals_player_block and self.applies_status_name is None
        )


class CardEffect(Protocol):
    """One rule operation. Complex cards can supply their own immutable effect."""

    def apply(self, card: Card, player: Player, target: Enemy | None) -> None: ...


@dataclass(frozen=True, slots=True)
class CardDefinition:
    definition_id: str
    levels: tuple[CardSpec, ...]
    effects: tuple[CardEffect, ...]

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

    @property
    def spec(self) -> CardSpec:
        return self.definition.spec_at(self.upgrade_level)

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

    def play(self, player: Player, enemy: Enemy | None) -> None:
        for effect in self.definition.effects:
            effect.apply(self, player, enemy)

    def __repr__(self) -> str:
        return f"{self.name}(cost={self.cost}, exhausts={self.exhausts})"
