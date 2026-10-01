"""Per-observation card reuse preserves dynamic views and public identities."""
from copy import deepcopy

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.headless import HeadlessAdapter
from game.agent.headless.full_cards import CardViews, card_node, signature
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine


def test_reused_views_match_every_card_definition_and_upgrade():
    views = CardViews()
    for definition in DEFAULT_CARDS.definitions:
        for level in range(len(definition.levels)):
            card = DEFAULT_CARDS.create(definition.definition_id, upgrade_level=level)
            assert views.signature(card) == signature(card)
            assert views.card(card, 'card:9') == card_node(card, 'card:9')
            assert views.card(card).ref is None
            assert views.card(card, 'card:12').ref == 'card:12'


def test_reused_views_separate_pile_costs_and_refresh_mutable_card_state():
    run = RunEngine(config=RunConfig(character='regent'), card_ids=('strike', 'mad_science'))
    run.start_combat(cards_per_turn=2)
    player = run.combat.player
    player.rules.powers['void_form'] = 2
    player.rules.auxiliaries['void_form'] = 0
    views = CardViews(player)
    card = next(c for c in player.hand if c.definition.definition_id == 'strike')
    assert views.card(card).get('energy') == 1
    assert views.card(card, on_table=True).get('energy') == 0
    for on_table in (False, True):
        assert views.card(card, 'card:4', on_table=on_table) == card_node(
            card, 'card:4', player, on_table=on_table)

    prior = views.card(card)
    card.upgrade()
    card.permanent_damage = 7
    card.combat_state.hexed = True
    player.rules.powers.clear()
    fresh = CardViews(player)
    assert fresh.card(card) == card_node(card, player=player) != prior
    assert fresh.signature(card) == signature(card, player)
    science = next(c for c in player.hand if c.definition.definition_id == 'mad_science')
    previous = fresh.card(science)
    science.event_data['kind'] = 'skill'
    assert CardViews(player).card(science) == card_node(science, player=player) != previous


@pytest.mark.parametrize('seed', (0, 7))
def test_cached_projection_matches_uncached_across_draws_and_actions(seed, monkeypatch):
    import game.agent.headless.full_projection as projection

    class UncachedViews:
        def __init__(self, player=None):
            self.player = player

        def card(self, card, ref=None, *, on_table=False):
            return card_node(card, ref, self.player, on_table=on_table)

        def signature(self, card):
            return signature(card, self.player)

    run = RunEngine(seed=seed, config=RunConfig(), card_ids=(
        'strike', 'strike', 'strike', 'defend', 'defend', 'bash', 'pommel_strike', 'shrug_it_off'))
    run.start_combat(cards_per_turn=3)
    left = HeadlessAdapter(run, decision_profile=f.PROFILE)
    right = HeadlessAdapter(deepcopy(run), decision_profile=f.PROFILE)
    for _ in range(40):
        before = left._engine.snapshot()
        a = left.observe()
        with monkeypatch.context() as patch:
            patch.setattr(projection, 'CardViews', UncachedViews)
            b = right.observe()
        assert left._engine.snapshot() == before == right._engine.snapshot()
        if isinstance(a, c.RunOutcome):
            assert a == b
            break
        assert a.decision == b.decision
        chosen = choose_action(a.decision)
        assert left.step(a.binding, chosen.ref) == right.step(b.binding, chosen.ref)
        assert left._engine.snapshot() == right._engine.snapshot()
        if left._engine.combat is None:
            break  # This authored combat fixture has no subsequent route.
