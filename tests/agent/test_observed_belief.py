"""Revealed transitions, conditioning likelihoods and attachment boundaries."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest

from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd
from game.agent.headless import HeadlessAdapter
from game.agent.headless.full_projection import FullProjection
from game.agent.headless.identity import Identities
from game.agent.input_views import planning_view
from game.agent.search import SearchPolicy, SearchConfig
from game.agent.search.belief import BeliefBudget
from game.agent.search.observed import ANCHOR, MODEL, ObservedCombatBelief
from game.agent.search.public_keys import public_key
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.characters import potion_pool
from game.headless.draw_knowledge import InconsistentKnowledge
from game.headless.generation.combat import select_cards
from game.headless.reveals import CombatReveals, run_reveals, reveal_owners, validate_reveals
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.snapshots import restore_run
from .test_belief import hand, play
from .test_search import UniformPolicy


def fixture(deck, *, potions=(), relics=('burning_blood',), seed=2, hp=70):
    run = RunEngine(seed=seed, card_ids=deck, hp=hp, max_hp=80,
                    config=RunConfig(reward_potions=potion_pool('ironclad')), rng_profile='native')
    for name in relics:
        run.obtain_relic(name)
    from game.headless.run.inventory import add_potion
    for name in potions:
        add_potion(run.state, name)
    initial = f.PublicDecision('sts_public_decision_v2', f.PROFILE,
        FullProjection(run, Identities(), [], {}, 'attachment', 0, False).run(),
        f.Node('map', 'map'), (f.Candidate('action:0', 'end_turn'),))
    with run_reveals(run) as journal:
        run.start_combat(encounter_id='overgrowth_vantom')
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    opening = adapter.observe().decision
    anchor = dict(schema=ANCHOR, initial=f.to_dict(initial), opening=f.to_dict(opening),
                  opening_reveals=journal.events, transitions=[])
    belief = ObservedCombatBelief(anchor, opening, seed=90,
        budget=BeliefBudget(2, 1024, 10., replay_proposals=128))
    assert belief.recover().reason is None
    return run, adapter, belief, anchor


def advance(run, adapter, belief, action, anchor=None):
    before = adapter.observe()
    snapshot = run.snapshot()
    plain = restore_run(snapshot)
    reference = HeadlessAdapter(plain, decision_profile=f.PROFILE)
    rf = reference.observe()
    from game.agent.search.public_keys import action_key
    other = next(a for a in rf.decision.candidates if action_key(rf.decision, a) == action_key(before.decision, action))
    reference.step(rf.binding, other.ref)
    with run_reveals(run) as journal:
        receipt = adapter.step(before.binding, action.ref)
    assert run.snapshot() == plain.snapshot(), 'Recording changed state/RNG'
    successor = adapter.combat_completion or adapter.observe().decision
    belief.receive_reveals(journal.events)
    update = belief.observe_transition(before.decision, action, receipt, successor)
    assert update.reason is None, update
    if anchor is not None and not isinstance(successor, CombatEnd):
        anchor['transitions'].append(dict(action_ref=action.ref, successor=f.to_dict(successor), reveals=journal.events))
    if not isinstance(successor, CombatEnd):
        assert public_key(belief.sample(45)[1]) == public_key(planning_view(successor))
    return successor, journal.events


@pytest.mark.parametrize('name', ('pillage', 'infernal_blade', 'havoc', 'juggling', 'hellraiser',
                                   'stoke', 'second_wind', 'aggression'))
def test_previous_card_coverage_gaps_execute_and_condition(name):
    # Five cards guarantees the source is drawn; later turns exercise reshuffle,
    # retained copies, triggered draw and autoplay under the same mechanism.
    run, adapter, belief, _ = fixture((name, 'strike', 'strike', 'defend', 'poor_sleep'))
    action = play(belief.current, name)
    advance(run, adapter, belief, action)
    for _ in range(10):
        current = adapter.observe().decision
        selected = [a for a in current.candidates if a.kind in ('select_card', 'confirm_selection')]
        if selected:
            action = selected[-1]
        else:
            playable = [a for a in current.candidates if a.kind == 'play_card']
            action = playable[0] if playable else next(a for a in current.candidates if a.kind == 'end_turn')
        result, _ = advance(run, adapter, belief, action)
        if isinstance(result, CombatEnd):
            break


@pytest.mark.parametrize('name', ('bottled_potential', 'colorless_potion', 'fysh_oil',
    'liquid_memories', 'radiant_tincture', 'stable_serum', 'entropic_brew', 'snecko_oil',
    'droplet_of_precognition'))
def test_potion_generation_draw_movement_selectors_and_costs(name):
    run, adapter, belief, _ = fixture(('strike', 'defend', 'bash', 'strike', 'defend', 'anger', 'defend'),
                                      potions=(name,))
    current = belief.current
    plays = [a for a in current.candidates if a.kind == 'play_card']
    if name == 'liquid_memories':
        current, _ = advance(run, adapter, belief, plays[0])
    action = next(a for a in current.candidates if a.kind == 'use_potion')
    current, _ = advance(run, adapter, belief, action)
    for _ in range(6):
        if isinstance(current, CombatEnd): break
        selectors = [a for a in current.candidates if a.kind in ('select_card', 'confirm_selection')]
        if not selectors: break
        current, _ = advance(run, adapter, belief, selectors[-1])
    if not isinstance(current, CombatEnd):
        advance(run, adapter, belief, next(a for a in current.candidates if a.kind == 'end_turn'))


def test_end_turn_transient_draw_retention_and_opening_upgrade():
    run, adapter, belief, _ = fixture(('clumsy', 'poor_sleep', 'strike', 'defend', 'defend', 'strike', 'defend'),
        relics=('burning_blood', 'centennial_puzzle', 'bellows'))
    for _ in range(3):
        current = adapter.observe().decision
        advance(run, adapter, belief, next(a for a in current.candidates if a.kind == 'end_turn'))


def test_prefix_restores_knowledge_but_rebases_public_attachment():
    run, adapter, belief, anchor = fixture(('headbutt', 'strike', 'pommel_strike', 'defend', 'defend'))
    for name in ('strike', 'headbutt'):
        current, _ = advance(run, adapter, belief, play(belief.current, name), anchor)
    attached = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
    later = ObservedCombatBelief(anchor, attached, seed=7, budget=BeliefBudget(2, 64, 10))
    assert later.recover().reason is None
    for seed in range(10):
        world, public = later.sample(seed)
        assert public_key(public) == public_key(planning_view(attached))
        assert world._run.combat.player.deck.draw_pile[-1].definition.definition_id == 'strike'


def test_fixed_seed_search_ignores_actual_rng_order_and_private_card_names():
    run, adapter, belief, anchor = fixture(('strike', 'defend') * 5)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.player.deck.rng.random()
    run.combat.player.deck.generation_rng.random()
    # Rename every card consistently via the private snapshot, never the anchor.
    snapshot = run.snapshot()
    import json
    raw = json.dumps(snapshot)
    for i, identity in enumerate(sorted(run.combat.player.deck._allocated_ids, key=len, reverse=True)):
        raw = raw.replace('"' + identity + '"', '"private-renamed-' + str(i) + '"')
    other = restore_run(json.loads(raw))
    second = HeadlessAdapter(other, decision_profile=f.PROFILE).observe().decision
    assert public_key(first) == public_key(second)
    results = []
    for observation in (first, second):
        policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=8,
            seed=13, time_limit=30, belief_seconds=10, belief_particles=2))
        policy.begin_combat(anchor, observation)
        result = policy.choose(observation)
        assert result.reason is None
        results.append((result.action_ref, result.probabilities, result.values, result.visits))
    assert results[0] == results[1]


def test_distinct_generation_likelihood_and_journal_integrity():
    from game.headless.core.native_rng import NativeRng
    options = [DEFAULT_CARDS.definition(n) for n in ('strike', 'defend', 'bash')]
    expected = [dict(kind='generated_cards', value=['bash', 'defend'])]
    rng, control = NativeRng(9), NativeRng(9)
    journal = CombatReveals(expected)
    with reveal_owners([rng], journal):
        selected = select_cards(options, rng, 2, distinct=True, revealed=True)
    select_cards(options, control, 2, distinct=True)
    journal.finish()
    assert [d.definition_id for d in selected] == ['bash', 'defend']
    assert math.exp(journal.log_likelihood) == pytest.approx(1/6)
    assert rng.getstate() == control.getstate()
    for malformed in ([dict(kind='rng', value=1)], [dict(kind='draw', value=['strike', 0], private_id='x')]):
        with pytest.raises(ValueError): validate_reveals(malformed)
    with pytest.raises(InconsistentKnowledge): CombatReveals(expected).finish()


def test_invisible_generated_potion_is_not_recorded():
    run, adapter, belief, _ = fixture(('alchemize', 'defend', 'defend', 'defend', 'defend'),
        potions=('fire_potion', 'block_potion', 'strength_potion'))
    _, events = advance(run, adapter, belief, play(belief.current, 'alchemize'))
    assert not events


def test_missing_reveal_receipt_invalidates_belief():
    run, adapter, belief, _ = fixture(('strike', 'defend'))
    before = adapter.observe()
    action = next(a for a in before.decision.candidates if a.kind == 'end_turn')
    receipt = adapter.step(before.binding, action.ref)
    from game.headless.planning import UnsupportedSearch
    with pytest.raises(UnsupportedSearch, match='missing_combat_reveals'):
        belief.observe_transition(before.decision, action, receipt, adapter.observe().decision)


def test_receipt_sequences_normalize_to_json_lists():
    expected = ({'kind': 'draw', 'value': ('strike', 0)},)
    journal = CombatReveals(expected)
    journal.card(DEFAULT_CARDS.create('strike'), 'draw')
    journal.finish()
    assert journal.events == [{'kind': 'draw', 'value': ['strike', 0]}]


def test_displayed_cost_conditioning_marginalizes_hidden_setters():
    full = CombatReveals([dict(kind='random_cost', value=0)], seed=3)
    assert full.cost(2, [0, 0, 0, 0]) in range(4)
    assert full.log_likelihood == 0.
    partial = CombatReveals([dict(kind='random_cost', value=0)], seed=3)
    assert partial.cost(3, [0, 0, 1, 2]) in (0, 1)
    assert math.exp(partial.log_likelihood) == pytest.approx(.5)


def test_masked_random_costs_have_identical_public_journals_and_search():
    from game.headless.core.native_rng import NativeRng
    run, adapter, belief, anchor = fixture(('corruption', 'defend', 'defend', 'defend', 'defend'),
                                           potions=('snecko_oil',))
    advance(run, adapter, belief, play(belief.current, 'corruption'), anchor)
    results, observations, receipts, raw = [], [], [], []
    for seed in (1, 13):
        other = restore_run(run.snapshot())
        other.combat.player.deck.energy_rng.setstate(NativeRng(seed).getstate())
        projection = HeadlessAdapter(other, decision_profile=f.PROFILE)
        before = projection.observe()
        action = next(a for a in before.decision.candidates if a.kind == 'use_potion')
        # This is a separate public attachment; preserve its continuous prefix.
        initial = projection.observe().decision
        # Search at this boundary uses a replayed public prefix with the same
        # action key, then rebases to this new attachment.
        policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=4,
            seed=18, time_limit=30, belief_seconds=10, belief_particles=2))
        policy.begin_combat(anchor, initial)
        with run_reveals(other) as journal:
            receipt = projection.step(before.binding, action.ref)
        after = projection.observe().decision
        policy.observe_reveals(journal.events)
        policy.observe_transition(initial, action, receipt, after)
        observations.append(public_key(after)); receipts.append(journal.events)
        raw.append([c.combat_state.turn_cost_override for c in other.combat.player.hand])
        result = policy.choose(after)
        assert result.reason is None
        results.append((result.action_ref, result.probabilities, result.values, result.visits))
    assert raw[0] != raw[1]
    assert observations[0] == observations[1] and receipts[0] == receipts[1]
    assert all(e['value'] == 0 for e in receipts[0] if e['kind'] == 'random_cost')
    assert results[0] == results[1]


def test_hidden_generation_is_not_journaled():
    from game.headless.core.native_rng import NativeRng
    journal, rng = CombatReveals(), NativeRng(3)
    options = [DEFAULT_CARDS.definition(n) for n in ('strike', 'defend', 'bash')]
    with reveal_owners([rng], journal):
        select_cards(options, rng, 3, distinct=False)
    assert journal.events == []


def test_random_insertions_preserve_particle_order_constraints():
    from game.headless.draw_knowledge import DrawKnowledge
    from game.headless.core.deck import Deck
    from random import Random
    cards = [DEFAULT_CARDS.create(n, instance_id=str(i)) for i, n in enumerate(
        ('strike', 'defend', 'bash', 'pommel_strike'))]
    possible_tops = []
    for index in range(5):
        deck = Deck(deepcopy(cards), Random(0))
        deck.draw_pile.sort(key=lambda c: c.instance_id)
        knowledge = DrawKnowledge(top=['3'], bottom=['0'])
        deck.rng.draw_knowledge = knowledge
        added = DEFAULT_CARDS.create('wound', instance_id='4')
        deck.insert_into_draw(index, added)
        knowledge.materialize(deck)
        possible_tops.append(deck.draw_pile[-1].definition.definition_id)
        assert deck.draw_pile[0].definition.definition_id == ('wound' if index == 0 else 'strike')
    assert possible_tops == ['pommel_strike'] * 4 + ['wound']
