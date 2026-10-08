"""Public fresh-inventory setup declaration for maintained combat beliefs.

This deliberately does not attach to an arbitrary observed fight. Every card
is a fresh template, every relic has an explicit counter and empty instance
data, and the encounter has been publicly revealed. An adapter must establish
that provenance before constructing this record. Native production is deferred.
"""
from dataclasses import dataclass
from typing import Literal

from .codec import ContractError, _read, _read_record, _wire
from .full import Node, PublicDecision, Candidate, require_ready


@dataclass(frozen=True, slots=True)
class StartingCard:
    definition_id: str
    upgrade_level: int


@dataclass(frozen=True, slots=True)
class StartingRelic:
    definition_id: str
    counter: int


@dataclass(frozen=True, slots=True)
class CombatStart:
    schema: Literal['sts_declared_combat_start_v1']
    provenance: Literal['declared_fresh_inventory']
    card_catalog: str
    character: Literal['ironclad']
    ascension: Literal[0]
    encounter_id: str
    hp: int
    max_hp: int
    gold: int
    deck: tuple[StartingCard, ...]
    relics: tuple[StartingRelic, ...]
    potions: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class CombatEnd:
    """Public run inventory/HUD after verified combat cleanup, not run victory."""
    result: Literal['victory', 'defeat']
    run: Node


def validate_start(value):
    value = _read_record(value, CombatStart, '$')
    if (not value.card_catalog or not value.encounter_id or
            not 0 < value.hp <= value.max_hp or value.gold < 0 or
            not 1 <= len(value.deck) <= 128 or len(value.relics) > 32 or
            not 1 <= len(value.potions) <= 8):
        raise ContractError('Invalid declared combat setup')
    for card in value.deck:
        if not card.definition_id or card.upgrade_level < 0:
            raise ContractError('Invalid starting card')
    for relic in value.relics:
        if not relic.definition_id or relic.counter < 0:
            raise ContractError('Invalid starting relic counter')
    if any(name == '' for name in value.potions):
        raise ContractError('Invalid starting potion')
    return value


def from_dict(value):
    return validate_start(_read(value, CombatStart, '$'))


def to_dict(value):
    return _wire(validate_start(value))


def validate_end(value):
    value = _read_record(value, CombatEnd, '$')
    # Reuse the existing graph/reference/capacity validation without claiming
    # that this synthetic validation candidate is a real post-combat action.
    require_ready(PublicDecision('sts_public_decision_v2', 'full_run_v2', value.run,
                                Node('terminal', 'combat_complete'), (Candidate('action:0', 'end_turn'),)))
    hp, maximum = value.run.get('hp'), value.run.get('max_hp')
    if (type(hp) is not int or type(maximum) is not int or not 0 <= hp <= maximum or
            maximum <= 0 or (hp == 0) != (value.result == 'defeat')):
        raise ContractError('Invalid settled combat HUD/outcome')
    return value


def end_to_dict(value):
    return _wire(validate_end(value))


def end_from_dict(value):
    return validate_end(_read(value, CombatEnd, '$'))
