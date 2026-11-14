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


def _combat(seed=0):
    run = RunEngine(seed=seed, config=RunConfig(), card_ids=(
        'strike', 'strike', 'strike', 'defend', 'defend', 'bash', 'pommel_strike', 'shrug_it_off'))
    run.start_combat(cards_per_turn=3)
    return run


@pytest.mark.parametrize('seed', (0, 7))
def test_search_worlds_adopt_their_projection_and_match_a_copied_one(seed, monkeypatch):
    from game.agent.headless.full_projection import FullProjection
    from game.agent.search.public_keys import action_key
    from game.agent.search.world import SimulationWorld
    copies = []
    original = f._clone_decision
    monkeypatch.setattr(f, '_clone_decision', lambda value: copies.append(value) or original(value))
    world = SimulationWorld(_combat(seed))
    observation = world.project()
    for _ in range(40):
        assert not copies, 'A search world copied the observation it had just built'
        assert world.prepared.value is observation and f._exact_decision(observation)
        copied = FullProjection(world._run, world._ids, world._history, world._powers, 'attachment', 0, False).decision()
        assert copied == observation and copied is not observation and copies.pop() is not None
        chosen = choose_action(observation)
        observation = world.step(observation, action_key(observation, chosen))
        if observation is None:
            break


def test_the_adapter_still_returns_a_private_copy(monkeypatch):
    copies = []
    original = f._clone_decision
    monkeypatch.setattr(f, '_clone_decision', lambda value: copies.append(value) or original(value))
    public = HeadlessAdapter(_combat(), decision_profile=f.PROFILE).observe().decision
    assert copies and all(source is not public for source in copies)


def test_signatures_are_reused_across_observations_with_exact_types(monkeypatch):
    import game.agent.headless.full_cards as cards
    from game.agent.headless.full_cards import _reused_signature, _signature
    cards._SIGNATURES.clear()
    child_int = f.Node('spec', 'card_spec', fields=(f.Field('n', 1),))
    child_bool = f.Node('spec', 'card_spec', fields=(f.Field('n', True),))
    assert child_int == child_bool  # Python equality cannot tell them apart; their JSON can.
    variants = [f.Node('card', 'strike', fields=(f.Field('flag', value),), children=(child,))
                for value in (1, True, 0, False, None, '1') for child in (child_int, child_bool)]
    variants.append(f.Node('card', 'strike', 'card:1', fields=(f.Field('flag', 1),), children=(child_int,)))
    variants.append(f.Node('card', 'bash', fields=(f.Field('flag', 1),), children=(child_int,)))
    expected = [_signature(value) for value in variants]
    assert len(set(expected)) == len(expected)
    assert [_reused_signature(value) for value in variants] == expected
    # A second pass repeats no JSON, also for an equal description rebuilt around the same children.
    rebuilt = [f.Node(v.kind, v.definition_id, v.ref, v.fields, v.links, v.children) for v in variants]
    with monkeypatch.context() as patch:
        patch.setattr(cards, '_signature', lambda value: pytest.fail('Repeated a card signature'))
        assert [_reused_signature(value) for value in (*variants, *rebuilt)] == expected * 2
    # Equal children that are other objects only miss; the answer is unchanged.
    twin = f.Node('card', 'strike', fields=(f.Field('flag', 1),),
                  children=(f.Node('spec', 'card_spec', fields=(f.Field('n', 1),)),))
    assert _reused_signature(twin) == expected[0]
    # The bound clears wholesale and changes no answer.
    monkeypatch.setattr(cards, '_SIGNATURE_LIMIT', 3)
    cards._SIGNATURES.clear()
    for value in (*variants, *variants):
        assert _reused_signature(value) == _signature(value)
        assert len(cards._SIGNATURES) <= 3


def test_action_keys_walk_the_observation_once_and_match_single_keys(monkeypatch):
    import game.agent.search.public_keys as keys
    public = HeadlessAdapter(_combat(), decision_profile=f.PROFILE).observe().decision
    assert len(public.candidates) > 3
    single = [keys.action_key(public, a) for a in public.candidates]
    expected_public, expected_observation = keys.public_key(public), keys.observation_key(public)
    assert expected_public[2] == expected_observation[2] == tuple(single)
    walks = []
    original = keys._paths
    monkeypatch.setattr(keys, '_paths', lambda decision: walks.append(decision) or original(decision))
    assert keys.action_keys(public) == single and len(walks) == 1
    assert keys.action_keys(public, public.candidates[1:3]) == single[1:3] and len(walks) == 2
    assert keys.public_key(public) == expected_public and len(walks) == 3
    assert keys.observation_key(public) == expected_observation and len(walks) == 4
    assert keys.action_key(public, public.candidates[0], original(public)) == single[0] and len(walks) == 4
