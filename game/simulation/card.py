"""Card definitions for the minimal combat simulator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .status import VULNERABLE

if TYPE_CHECKING:
    from .enemy import Enemy
    from .player import Player


class Card(ABC):
    """Base class for a playable combat card."""

    def __init__(self, name: str, cost: int, exhausts: bool = False) -> None:
        self.name = name
        self.cost = cost
        self.exhausts = exhausts

    @abstractmethod
    def play(self, player: Player, enemy: Enemy) -> None:
        """Apply the card's effect to the combat state."""

    def __repr__(self) -> str:
        return f"{self.name}(cost={self.cost}, exhausts={self.exhausts})"


@dataclass(frozen=True, slots=True)
class CardSpec:
    """Static card metadata used for encoding and trace analysis."""

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
        """Return whether the card has no immediate tactical effect."""
        return (
            self.base_damage <= 0
            and self.block_gain <= 0
            and self.draw_count <= 0
            and not self.damage_equals_player_block
            and self.applies_status_name is None
        )


class StrikeCard(Card):
    """Starter attack card that deals 6 damage."""

    def __init__(self) -> None:
        super().__init__(name="Strike", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        enemy.take_damage(
            6,
            attacker_statuses=player.statuses,
            attacker_strength=player.strength,
        )


class DefendCard(Card):
    """Starter skill card that grants 5 block."""

    def __init__(self) -> None:
        super().__init__(name="Defend", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        player.gain_block(5)


class BashCard(Card):
    """Starter attack card that deals 8 damage and applies Vulnerable."""

    def __init__(self) -> None:
        super().__init__(name="Bash", cost=2)

    def play(self, player: Player, enemy: Enemy) -> None:
        enemy.take_damage(
            8,
            attacker_statuses=player.statuses,
            attacker_strength=player.strength,
        )
        enemy.apply_status(VULNERABLE, 2)


class PommelStrikeCard(Card):
    """Ironclad attack that deals 9 damage and draws one card."""

    def __init__(self) -> None:
        super().__init__(name="Pommel Strike", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        enemy.take_damage(
            9,
            attacker_statuses=player.statuses,
            attacker_strength=player.strength,
        )
        player.draw_cards(1)


class ShrugItOffCard(Card):
    """Ironclad skill that grants 8 block and draws one card."""

    def __init__(self) -> None:
        super().__init__(name="Shrug It Off", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        del enemy
        player.gain_block(8)
        player.draw_cards(1)


class IronWaveCard(Card):
    """Ironclad attack that gains 5 block before dealing 5 damage."""

    def __init__(self) -> None:
        super().__init__(name="Iron Wave", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        player.gain_block(5)
        enemy.take_damage(
            5,
            attacker_statuses=player.statuses,
            attacker_strength=player.strength,
        )


class BodySlamCard(Card):
    """Ironclad attack that deals damage equal to current player block."""

    def __init__(self) -> None:
        super().__init__(name="Body Slam", cost=1)

    def play(self, player: Player, enemy: Enemy) -> None:
        enemy.take_damage(
            player.block,
            attacker_statuses=player.statuses,
            attacker_strength=player.strength,
        )


class SlimedCard(Card):
    """Temporary status card shuffled in by slime enemies."""

    def __init__(self) -> None:
        super().__init__(name="Slimed", cost=1, exhausts=True)

    def play(self, player: Player, enemy: Enemy) -> None:
        del player, enemy
        return


def create_starter_deck() -> list[Card]:
    """Create the first-version starter deck."""
    return (
        [StrikeCard() for _ in range(5)]
        + [DefendCard() for _ in range(4)]
        + [BashCard()]
    )


def create_ironclad_sequencing_deck() -> list[Card]:
    """Create a non-canonical 10-card deck for sequencing experiments."""
    return (
        [StrikeCard() for _ in range(2)]
        + [DefendCard() for _ in range(3)]
        + [
            BashCard(),
            PommelStrikeCard(),
            ShrugItOffCard(),
            IronWaveCard(),
            BodySlamCard(),
        ]
    )


CARD_SPECS: dict[str, CardSpec] = {
    "Strike": CardSpec(
        name="Strike",
        cost=1,
        kind="attack",
        base_damage=6,
    ),
    "Defend": CardSpec(
        name="Defend",
        cost=1,
        kind="block",
        block_gain=5,
        uses_target=False,
    ),
    "Bash": CardSpec(
        name="Bash",
        cost=2,
        kind="attack",
        base_damage=8,
        applies_status_name=VULNERABLE,
        applies_status_stacks=2,
    ),
    "Pommel Strike": CardSpec(
        name="Pommel Strike",
        cost=1,
        kind="attack",
        base_damage=9,
        draw_count=1,
    ),
    "Shrug It Off": CardSpec(
        name="Shrug It Off",
        cost=1,
        kind="block",
        block_gain=8,
        draw_count=1,
        uses_target=False,
    ),
    "Iron Wave": CardSpec(
        name="Iron Wave",
        cost=1,
        kind="attack",
        base_damage=5,
        block_gain=5,
    ),
    "Body Slam": CardSpec(
        name="Body Slam",
        cost=1,
        kind="attack",
        damage_equals_player_block=True,
    ),
    "Slimed": CardSpec(
        name="Slimed",
        cost=1,
        kind="status",
        exhausts=True,
        uses_target=False,
    ),
}


def get_card_spec(card_name: str) -> CardSpec:
    """Return static metadata for a known card name."""
    try:
        return CARD_SPECS[card_name]
    except KeyError as exc:
        raise ValueError(f"Unknown card name for metadata lookup: {card_name!r}") from exc
