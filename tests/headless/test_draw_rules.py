"""Pinned ordinary draw limits; native hooks and RNG parity are separate work."""

from copy import deepcopy
import json
from random import Random

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.deck import Deck
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.engine import RunEngine


def _deck(*, hand=0, draw=0, discard=0, exhaust=0):
    cards = [DEFAULT_CARDS.create("strike") for _ in range(hand + draw + discard + exhaust)]
    deck = Deck(cards, Random(43))
    # Authored pile order isolates draw semantics from the initial shuffle.
    deck.hand = cards[:hand]
    deck.draw_pile = cards[hand:hand + draw]
    deck.discard_pile = cards[hand + draw:hand + draw + discard]
    deck.exhaust_pile = cards[hand + draw + discard:]
    return deck


def _state(deck):
    return (
        tuple(tuple(c.instance_id for c in pile) for pile in
              (deck.hand, deck.draw_pile, deck.discard_pile, deck.exhaust_pile)),
        deck.rng.getstate(), deck._next_instance_id, frozenset(deck._allocated_ids),
    )


@pytest.mark.parametrize("hand, requested, expected", ((0, 14, 10), (8, 1, 1), (8, 2, 2), (8, 5, 2)))
def test_draw_stops_at_ten_without_moving_overflow(hand, requested, expected):
    deck = _deck(hand=hand, draw=14, discard=3, exhaust=1)
    before = _state(deck)
    original_draw = list(deck.draw_pile)
    drawn = deck.draw(requested)
    assert drawn == list(reversed(original_draw[-expected:]))
    assert len(deck.hand) == hand + expected
    assert deck.draw_pile == original_draw[:-expected]
    assert _state(deck)[0][2:] == before[0][2:]
    assert _state(deck)[1:] == before[1:]


@pytest.mark.parametrize("hand, draw", ((10, 0), (10, 3), (12, 0)))
def test_full_or_overfull_hand_does_not_reshuffle_or_discard(hand, draw):
    deck = _deck(hand=hand, draw=draw, discard=4)
    before = _state(deck)
    assert deck.draw(5) == []
    assert _state(deck) == before


def test_last_available_slot_does_not_trigger_a_subsequent_refill():
    deck = _deck(hand=9, draw=1, discard=4)
    before_rng = deck.rng.getstate()
    discard = list(deck.discard_pile)
    assert len(deck.draw(5)) == 1
    assert len(deck.hand) == 10 and deck.draw_pile == []
    assert deck.discard_pile == discard and deck.rng.getstate() == before_rng


def test_multi_draw_refills_only_when_needed_then_stops_at_capacity():
    deck = _deck(hand=8, draw=1, discard=4, exhaust=1)
    original = _state(deck)
    first = deck.draw_pile[-1]
    expected_rng = Random()
    expected_rng.setstate(deck.rng.getstate())
    expected_pile = list(deck.discard_pile)
    expected_rng.shuffle(expected_pile)
    second = expected_pile.pop()
    assert deck.draw(5) == [first, second]
    assert deck.draw_pile == expected_pile and deck.discard_pile == []
    assert deck.rng.getstate() == expected_rng.getstate()
    assert _state(deck)[0][3] == original[0][3]
    assert _state(deck)[2:] == original[2:]
    ids = [c.instance_id for pile in (deck.hand, deck.draw_pile, deck.exhaust_pile) for c in pile]
    assert len(ids) == len(set(ids)) == 14


def test_zero_empty_and_invalid_draws_leave_state_unchanged():
    deck = _deck(hand=8, discard=4)
    before = _state(deck)
    assert deck.draw(0) == []
    with pytest.raises(ValueError, match="negative"):
        deck.draw(-1)
    assert _state(deck) == before
    empty = _deck(hand=2, exhaust=3)
    before = _state(empty)
    assert empty.draw(4) == []
    assert _state(empty) == before


def test_card_draw_opens_a_slot_and_continues_after_snapshot_without_redrawing_itself():
    run = RunEngine(seed=43, card_ids=("pommel_strike",) * 10)
    combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=200), cards_per_turn=14)
    assert len(combat.player.hand) == 10
    first = combat.player.hand[0].instance_id
    combat.apply(PlayCard(first, 0))
    # The resolving card enters discard only after its draw; no other cards exist.
    assert len(combat.player.hand) == 9
    assert [c.instance_id for c in combat.player.deck.discard_pile] == [first]
    saved = json.loads(json.dumps(run.snapshot()))
    restored = RunEngine()
    restored.restore(saved)
    for action in (PlayCard(combat.player.hand[0].instance_id, 0), EndTurn()):
        assert combat.apply(action) == restored.combat.apply(action)
        assert run.snapshot() == restored.snapshot()
        assert len(combat.player.hand) <= 10
    assert len(combat.player.hand) == 10
    assert len(run.state.deck) == 10


def test_restored_full_hand_blocks_draw_without_advancing_rng():
    run = RunEngine(card_ids=("strike",) * 14)
    combat = run.start_combat(cards_per_turn=14)
    deck = combat.player.deck
    deck.discard_pile = deck.draw_pile
    deck.draw_pile = []
    saved = json.loads(json.dumps(run.snapshot()))
    restored = RunEngine()
    restored.restore(deepcopy(saved))
    for engine in (run, restored):
        assert engine.combat.player.draw_cards(3) == []
        assert json.loads(json.dumps(engine.snapshot())) == saved
