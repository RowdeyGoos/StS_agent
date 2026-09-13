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
    from game.headless.relics.run_rules import card_added
    card_added(state, card)
    return card


def remove_card(state: RunState, instance_id: str) -> Card:
    card = find_card(state, instance_id)
    if card.spec.eternal:
        raise ValueError("An Eternal card cannot be removed.")
    state.deck.remove(card)
    return card


def transform_card(state: RunState, cards, instance_id: str, replacement_pool, *, stream="card.transform") -> Card:
    """Replace an exact master-deck card in place with a fresh base-level instance.

    The caller owns source eligibility and pool composition. Validate all content
    before drawing; failed transformations preserve the card, allocator and RNG.
    """
    from game.headless.core.rng import GameRandomService
    state.validate()
    original = find_card(state, instance_id)
    if original.spec.eternal:
        raise ValueError("An Eternal card cannot be transformed.")
    pool = tuple(replacement_pool)
    if not pool or len(set(pool)) != len(pool):
        raise ValueError("Transformation requires a distinct replacement pool.")
    definitions = [cards.definition(name) for name in pool if name != original.definition.definition_id]
    if not definitions:
        raise ValueError("Transformation cannot reproduce the original definition.")
    for definition in definitions:
        definition.spec_at(0)
    rng = GameRandomService(state.seed)
    rng.restore(state.rng.snapshot())
    definition = rng.choice(stream, definitions)
    index = state.deck.index(original)
    replacement = Card(definition, instance_id=state.allocate_card_id())
    state.deck[index] = replacement
    state.rng = rng
    from game.headless.relics.run_rules import card_added
    card_added(state, replacement)
    return replacement


def replace_card(state: RunState, instance_id: str, definition) -> Card:
    """Deterministic fresh replacement in place, for explicit content results."""
    definition.spec_at(0)
    original = find_card(state, instance_id)
    index = state.deck.index(original)
    result = Card(definition, instance_id=state.allocate_card_id())
    state.deck[index] = result
    from game.headless.relics.run_rules import card_added
    card_added(state, result)
    return result


def commit_trial(state, trial):
    """Commit deck changes together with the relic effects those changes produced."""
    for field in ('deck', 'rng', 'next_card_id', 'hp', 'max_hp', 'gold', 'relics', 'next_item_id', 'relic_work'):
        setattr(state, field, getattr(trial, field))
