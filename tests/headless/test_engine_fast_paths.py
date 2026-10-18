"""Engine fast paths keep exact behavior: trusted legality, skipped re-checks, lookups and validation."""
import random

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.base import Card
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine


def fight(seed=7):
    run = RunEngine(seed=seed, config=RunConfig(), rng_profile='native',
                    card_ids=('strike',) * 4 + ('defend',) * 4 + ('bash', 'pommel_strike', 'shrug_it_off'))
    run.start_combat(encounter_id='overgrowth_vantom')
    return run


def test_trusted_legal_tuple_replays_exactly_and_still_rejects_other_actions():
    checked, trusted = fight(), fight()
    rng = random.Random(3)
    for _ in range(60):
        if checked.combat is None:
            break
        legal = checked.legal_actions()
        assert trusted.legal_actions() == legal
        action = rng.choice(legal)
        checked.apply(action)
        trusted.apply(action, legal=legal)
        assert trusted.snapshot() == checked.snapshot()
    run = fight()
    legal = run.legal_actions()
    with pytest.raises(ValueError, match='Illegal run action'):
        run.apply(PlayCard('missing.card'), legal=legal)
    with pytest.raises(ValueError, match='Illegal run action'):
        run.apply(EndTurn(), legal=tuple(a for a in legal if a != EndTurn()))


def test_combat_recheck_is_skipped_only_when_the_inventory_sync_changes_nothing(monkeypatch):
    calls = []
    original = CombatEngine.legal_actions
    monkeypatch.setattr(CombatEngine, 'legal_actions', lambda self: calls.append(1) or original(self))
    run = fight()
    run.apply(EndTurn())
    assert len(calls) == 1  # The run-level check alone.
    calls.clear()
    run.state.gold += 7  # Direct inventory change: the sync alters combat inputs before dispatch.
    run.apply(EndTurn())
    assert len(calls) == 2
    assert run.combat.player.rules.gold_available == run.state.gold


def test_deck_find_is_the_first_card_in_all_cards_order():
    run = fight()
    deck = run.combat.player.deck
    for card in deck.all_cards():
        assert deck.find(card.instance_id) is next(c for c in deck.all_cards() if c.instance_id == card.instance_id)
    assert deck.find('missing') is None


def test_card_spec_matches_levels_and_still_rejects_unsupported_levels():
    for definition in DEFAULT_CARDS.definitions:
        for level, spec in enumerate(definition.levels):
            if definition.definition_id != 'mad_science':
                assert Card(definition, upgrade_level=level).spec is spec
    card = DEFAULT_CARDS.create('strike')
    card.upgrade_level = 99
    with pytest.raises(ValueError, match='Unsupported upgrade level'):
        card.spec


def test_cached_initialization_reference_still_rejects_tampering():
    run = RunEngine.act1(seed=11)
    run.state.validate()
    snapshot = run.snapshot()
    snapshot['state']['initialization']['acts'][0]['boss'] = snapshot['state']['initialization']['acts'][1]['boss']
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)
    run.state.initialization['acts'][0]['normal'].reverse()
    with pytest.raises(ValueError, match='Native initialization differs'):
        run.state.validate()
