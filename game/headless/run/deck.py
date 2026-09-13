"""Persistent deck operations shared by upgrade/removal/reward sources."""

from game.headless.cards.base import Card
from game.headless.run.state import RunState


def find_card(state: RunState, instance_id: str) -> Card:
    try:
        return next(card for card in state.deck if card.instance_id == instance_id)
    except StopIteration as error:
        raise ValueError("Card instance is not in the persistent deck.") from error


def upgrade_card(state: RunState, instance_id: str) -> Card:
    # Legality of the upgrade source belongs to the calling room/event rule.
    state.validate()
    card = find_card(state, instance_id)
    card.upgrade()
    return card


def add_card(state: RunState, definition, *, upgrade_level: int = 0) -> Card:
    definition.spec_at(upgrade_level)  # Validate before consuming identity.
    card = Card(definition, upgrade_level=upgrade_level, instance_id=state.allocate_card_id())
    state.deck.append(card)
    return card


def remove_card(state: RunState, instance_id: str) -> Card:
    card = find_card(state, instance_id)
    state.deck.remove(card)
    return card
