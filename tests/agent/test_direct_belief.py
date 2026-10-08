"""Conditional distributions, public boundaries, and normal-engine execution."""
from collections import Counter
from dataclasses import replace
from itertools import permutations
import math
from random import Random

import pytest

from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd
from game.agent.full_policy import choose_action
from game.agent.headless import HeadlessAdapter
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.belief import BeliefBudget, _Work
from game.agent.search.direct import DirectCombatBelief, ENCOUNTERS, planning_view
from game.agent.search.public_keys import action_key, public_key
from game.agent.training.scenarios import Scenario
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.deck import Deck
from game.headless.core.native_rng import NativeRng
from game.headless.draw_knowledge import DrawKnowledge, HPKnowledge, InconsistentKnowledge
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.planning import UnsupportedSearch
from game.headless.run.snapshots import restore_run
from .test_belief import setup, actual, hand, play
from .test_search import UniformPolicy


def declared(deck, **kwargs):
    return setup(deck=deck, relics=(('burning_blood', 0),), **kwargs)


def direct(start, *, seed=5, particles=2):
    run, adapter = actual(start, seed=seed)
    belief = DirectCombatBelief(start, adapter.observe().decision, seed=41,
                                budget=BeliefBudget(particles, 128, 5, replay_proposals=128))
    return run, adapter, belief


def advance(adapter, belief, action):
    before = adapter.observe()
    report = adapter.step(before.binding, action.ref)
    after = adapter.combat_completion or adapter.observe().decision
    update = belief.observe_transition(before.decision, action, report, after)
    assert update.reason is None, update
    if not isinstance(after, CombatEnd):
        assert public_key(belief.sample(123)[1]) == public_key(planning_view(after))
    return after


def tiny_deck(names):
    cards = [DEFAULT_CARDS.create(name, instance_id=f'card.{i}') for i, name in enumerate(names)]
    return Deck(cards, NativeRng(3))


def test_conditional_duplicate_draw_matches_enumerated_distribution():
    # Six equiprobable physical orders; four start with Strike. Given that
    # observation, half the remaining next cards are Strike and half Defend.
    names = ('strike', 'strike', 'defend')
    orders = list(permutations(range(3)))
    accepted = [o for o in orders if names[o[-1]] == 'strike']
    assert len(accepted) / len(orders) == 2 / 3
    assert Counter(names[o[-2]] for o in accepted) == {'strike': 2, 'defend': 2}
    next_cards = Counter()
    physical = Counter()
    for seed in range(300):
        deck = tiny_deck(names)
        knowledge = DrawKnowledge()
        knowledge.condition([('strike', 0)], seed)
        deck.rng.draw_knowledge = knowledge
        knowledge.materialize(deck)
        card = deck.draw(1)[0]
        knowledge.finish()
        physical[card.instance_id] += 1
        assert math.exp(knowledge.log_likelihood) == pytest.approx(2 / 3)
        knowledge.condition(None, seed + 1000)
        knowledge.materialize(deck)
        next_cards[deck.draw(1)[0].definition.definition_id] += 1
    assert 115 <= next_cards['strike'] <= 185, next_cards
    assert len(physical) == 2


def test_known_ends_uniform_middle_and_shuffle_forgets_old_positions():
    deck = tiny_deck(('bash', 'strike', 'defend', 'wound'))
    knowledge = DrawKnowledge()
    deck.rng.draw_knowledge = knowledge
    top = next(c for c in deck.draw_pile if c.definition.definition_id == 'bash')
    bottom = next(c for c in deck.draw_pile if c.definition.definition_id == 'wound')
    for card, is_bottom in ((top, False), (bottom, True)):
        deck.draw_pile.remove(card)
        deck.put_on_draw(card, bottom=is_bottom)
    knowledge.condition([('bash', 0), ('strike', 0), ('defend', 0), ('wound', 0)], 12)
    knowledge.materialize(deck)
    assert [c.definition.definition_id for c in deck.draw(4)] == ['bash', 'strike', 'defend', 'wound']
    knowledge.finish()
    assert math.exp(knowledge.log_likelihood) == pytest.approx(.5)
    deck.discard_hand()
    deck._refill_draw_pile()
    assert knowledge.top == knowledge.bottom == []
    assert len(deck.draw_pile) == 4


def test_contradictory_known_draw_and_missing_or_extra_draws_reject():
    deck = tiny_deck(('bash', 'strike'))
    knowledge = DrawKnowledge(top=[next(c.instance_id for c in deck.draw_pile if c.definition.definition_id == 'bash')])
    deck.rng.draw_knowledge = knowledge
    knowledge.condition([('strike', 0)], 3)
    knowledge.materialize(deck)
    with pytest.raises(InconsistentKnowledge, match='known placement'):
        deck.draw(1)
    knowledge.condition([('bash', 0)], 4)
    with pytest.raises(InconsistentKnowledge, match='Missing'):
        knowledge.finish()
    knowledge.condition([], 5)
    with pytest.raises(InconsistentKnowledge, match='extra draw'):
        deck.draw(1)


def test_guidance_keeps_different_cost_lifetimes_on_duplicate_physical_cards():
    selected = Counter()
    for seed in range(40):
        deck = tiny_deck(('strike', 'strike'))
        deck.draw_pile[0].combat_state.free_until_played = True
        knowledge = DrawKnowledge()
        knowledge.condition([('strike', 0)], seed)
        deck.rng.draw_knowledge = knowledge
        card = deck.draw(1)[0]
        selected[card.combat_state.free_until_played] += 1
        assert knowledge.log_likelihood == 0.
    assert selected[False] and selected[True]


def test_initial_hp_uses_sequential_eligible_prior_and_preserves_rng_calls():
    natural, guided = NativeRng(9), NativeRng(9)
    plain = MonsterConstruction(NativeRng(8), natural)
    hp = HPKnowledge((27, 25))
    guided.hp_knowledge = hp
    conditional = MonsterConstruction(NativeRng(8), guided)
    # Three equally likely first HPs, then two excluding the forced first HP.
    assert [conditional.initial_hp(25, 27), conditional.initial_hp(25, 27)] == [27, 25]
    plain.initial_hp(25, 27)
    plain.initial_hp(25, 27)
    hp.finish()
    assert math.exp(hp.log_likelihood) == pytest.approx(1 / 6)
    assert conditional.used_hp == [27, 25]
    assert natural.counter == guided.counter
    guided.hp_knowledge = HPKnowledge((27, 27))
    conditional.used_hp.clear()
    conditional.initial_hp(25, 27)
    with pytest.raises(InconsistentKnowledge):
        conditional.initial_hp(25, 27)


@pytest.mark.parametrize('encounter', sorted(ENCOUNTERS))
def test_ordinary_openings_and_progress_use_direct_draws_without_prefix_replay(encounter):
    scenario = Scenario(encounter, 'controlled')
    run, adapter, belief = direct(scenario.planning_start(), seed=42)
    assert belief.last_update.proposals <= 64
    snapshot = run.snapshot()
    for seed in (1, 7, 21):
        world, decision = belief.sample(seed)
        assert public_key(decision) == public_key(planning_view(adapter.observe().decision))
        assert restore_run(world._run.snapshot()).snapshot() == world._run.snapshot()
    assert run.snapshot() == snapshot
    for _ in range(20):
        before = adapter.observe().decision
        after = advance(adapter, belief, choose_action(before))
        assert belief.last_update.replay_steps == 0
        if isinstance(after, CombatEnd):
            break


def test_headbutt_selection_draw_and_reshuffle_use_existing_rules():
    start = declared(('strike', 'headbutt', 'pommel_strike', 'defend', 'bash'))
    _, adapter, belief = direct(start)
    current = advance(adapter, belief, play(belief.current, 'strike'))
    current = advance(adapter, belief, play(current, 'headbutt'))
    for seed in range(8):
        world, _ = belief.sample(seed)
        assert world._run.combat.player.deck.draw_pile[-1].definition.definition_id == 'strike'
    current = advance(adapter, belief, play(current, 'pommel_strike'))
    assert hand(current)[-1].definition_id == 'strike'
    current = advance(adapter, belief, next(a for a in current.candidates if a.kind == 'end_turn'))
    assert belief.last_update.replay_steps == 0
    assert all(not w.knowledge.top for w in belief._worlds)


def test_pending_exhaust_selector_conditions_its_draw_once():
    start = declared(('burning_pact',) + ('strike',) * 3 + ('defend',) * 4)
    for seed in range(20):
        _, adapter, belief = direct(start, seed=seed)
        if any(n.definition_id == 'burning_pact' for n in hand(belief.current)):
            break
    current = advance(adapter, belief, play(belief.current, 'burning_pact'))
    assert any(n.kind == 'selection' for n in current.context.children)
    for seed in (3, 10):
        world, projected = belief.sample(seed)
        assert world._run.combat.player.pending_play is not None
        assert public_key(projected) == public_key(planning_view(current))
    old_size = len(hand(current))
    current = advance(adapter, belief, next(a for a in current.candidates if a.kind == 'select_card'))
    assert not any(n.kind == 'selection' for n in current.context.children)
    assert len(hand(current)) == old_size - 1 + 2


def test_potion_draw_and_lethal_cleanup_match_normal_engine():
    start = replace(declared(('bludgeon',) + ('strike',) * 3 + ('defend',) * 4),
                    encounter_id='overgrowth_nibbit', potions=('swift_potion', 'fire_potion', None))
    run, adapter, belief = direct(start)
    current = belief.current
    def potion(decision, definition):
        ref = next(n.ref for n in f.walk(decision.run) if n.kind == 'potion' and n.definition_id == definition)
        return next(a for a in decision.candidates if a.kind == 'use_potion' and a.subject == ref)
    current = advance(adapter, belief, potion(current, 'swift_potion'))
    assert len(hand(current)) == 8
    current = advance(adapter, belief, potion(current, 'fire_potion'))
    completed = advance(adapter, belief, play(current, 'bludgeon'))
    assert isinstance(completed, CombatEnd) and completed.result == 'victory'
    assert completed.run.get('hp') == run.state.hp == 76
    assert run.state.potions == [None, None, None]


def test_guided_recovery_retains_public_progress_without_actual_snapshots():
    _, adapter, belief = direct(declared(('strike',) * 4 + ('defend',) * 4))
    belief._invalidate('belief_budget')
    belief.budget = BeliefBudget(2, 2, 5, replay_proposals=0)
    before = adapter.observe()
    action = choose_action(before.decision)
    receipt = adapter.step(before.binding, action.ref)
    after = adapter.observe().decision
    assert belief.observe_transition(before.decision, action, receipt, after).reason == 'belief_budget'
    assert len(belief.transitions) == 1
    belief.budget = BeliefBudget(2, 128, 5, replay_proposals=128)
    update = belief.recover()
    assert update.recovered and update.reason is None and update.replay_steps == 2
    assert public_key(belief.sample(17)[1]) == public_key(planning_view(after))


def test_weighted_known_position_posterior_applies_likelihood_once():
    start = declared(('pommel_strike', 'strike', 'strike', 'strike', 'defend', 'defend', 'defend'))
    for seed in range(50):
        run, adapter, belief = direct(start, seed=seed)
        draw = run.combat.player.deck.draw_pile
        if Counter(c.definition.definition_id for c in draw) == {'strike': 1, 'defend': 1} and any(
                n.definition_id == 'pommel_strike' for n in hand(belief.current)):
            break
    else:
        pytest.fail('Missing tiny conditional fixture')
    unknown = belief._worlds[0]
    known = unknown.fork(1)
    known.knowledge.top = [next(c.instance_id for c in known._run.combat.player.deck.draw_pile
                                if c.definition.definition_id == 'strike')]
    unknown.tag, known.tag = 'unknown', 'known'
    before = belief.current
    action = play(before, 'pommel_strike')
    observed = known.fork(2)
    after = observed.step(observed.project(), action_key(before, action))
    proposals = iter((unknown, known))
    belief._condition(lambda: belief._advance(next(proposals), before, action, after), 2, _Work(5))
    assert belief.reason is None
    assert belief.weights == pytest.approx((1 / 3, 2 / 3))
    belief.weights = (1., 0.)
    assert all(belief._parent(Random(seed)).tag == 'unknown' for seed in range(10))


@pytest.mark.parametrize('leaf_steps', [0, 4])
def test_private_order_rng_names_and_latent_state_do_not_change_fixed_seed_search(leaf_steps):
    scenario = Scenario('overgrowth_slimes', 'controlled')
    run = scenario.make(42)
    first = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.rng.random()
    # This private latch is not part of the advertised current intent.
    run.combat.enemies[0].turn_roll_pending = not run.combat.enemies[0].turn_roll_pending
    deck = run.combat.player.deck
    mapping = {card.instance_id: 'renamed.' + card.instance_id for card in deck.all_cards()}
    for card in deck.all_cards():
        card.instance_id = mapping[card.instance_id]
    deck.original_ids = {mapping[i] for i in deck.original_ids}
    deck._allocated_ids = {mapping[i] for i in deck._allocated_ids}
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert public_key(first) == public_key(second)
    config = SearchConfig(model_version='direct_belief_v1', simulations=16, max_depth=8,
                          time_limit=10, belief_particles=2, belief_proposals=128, seed=7,
                          leaf_rollout_steps=leaf_steps)
    left, right = SearchPolicy(UniformPolicy(), config), SearchPolicy(UniformPolicy(), config)
    left.begin_combat(scenario.planning_start(), first)
    right.begin_combat(scenario.planning_start(), second)
    snapshot = run.snapshot()
    a, b = left.choose(first), right.choose(second)
    assert a.reason is b.reason is None and a.simulations == b.simulations == 16
    assert (a.action_ref, a.probabilities, a.values, a.visits) == (b.action_ref, b.probabilities, b.values, b.visits)
    assert a.leaf_work == b.leaf_work
    assert run.snapshot() == snapshot


def test_history_card_aliases_are_removed_from_real_and_simulated_network_inputs():
    _, adapter, belief = direct(declared(('strike',) * 5 + ('defend',) * 4 + ('bash',)))
    current = advance(adapter, belief, play(belief.current, 'strike'))
    public = planning_view(current)
    assert public.candidates == current.candidates and public.context == current.context
    assert any(link.targets for n in f.walk(current.run) for link in n.links if link.key == 'history_subject')
    assert not any(link.targets for n in f.walk(public.run) for link in n.links if link.key == 'history_subject')
    seen = []
    base = UniformPolicy()
    original = base.probabilities
    base.probabilities = lambda d: (seen.append(d), original(d))[1]
    owner = SearchPolicy(base, SearchConfig(model_version='direct_belief_v1', simulations=4, time_limit=10))
    owner.belief = belief
    result = owner.choose(current)
    assert result.reason is None
    assert seen and all(not any(link.targets for n in f.walk(d.run) for link in n.links
                               if link.key == 'history_subject') for d in seen)
    assert belief.current == current  # Original public journal stays intact.


def test_inconsistent_successor_and_budget_exhaustion_do_not_serve_stale_worlds():
    _, adapter, belief = direct(declared(('strike', 'defend')))
    before = belief.current
    action = play(before, 'strike')
    receipt = adapter.step(adapter.observe().binding, action.ref)
    after = adapter.observe().decision
    after = replace(after, run=replace(after.run, fields=tuple(
        f.Field(v.key, v.value + 1) if v.key == 'gold' else v for v in after.run.fields)))
    belief.budget = BeliefBudget(2, 2, 5, replay_proposals=2)
    assert belief.observe_transition(before, action, receipt, after).reason == 'belief_budget'
    with pytest.raises(UnsupportedSearch, match='belief_budget'):
        belief.sample(1)
    assert belief.recover(seconds=0).reason == 'belief_budget'


def test_unsupported_sources_fallback_explicitly_without_changing_model():
    start = declared(('infernal_blade', 'strike'))
    _, adapter = actual(start)
    config = SearchConfig(model_version='direct_belief_v1', simulations=4)
    owner = SearchPolicy(UniformPolicy(), config)
    owner.begin_combat(start, adapter.observe().decision)
    result = owner.choose(adapter.observe().decision)
    assert result.reason == 'direct_setup_unsupported'
    assert result.simulations == 0 and result.action_ref in {a.ref for a in adapter.observe().decision.candidates}
    owner.reset()
    assert owner.choose(adapter.observe().decision).reason == 'missing_planning_anchor'


def test_invalid_engine_setup_values_return_named_fallback():
    from game.agent.contracts.planning import StartingCard
    start = declared(('strike', 'defend'))
    _, adapter = actual(start)
    start = replace(start, deck=(StartingCard('strike', 2), *start.deck[1:]))
    owner = SearchPolicy(UniformPolicy(), SearchConfig(model_version='direct_belief_v1', simulations=4))
    owner.begin_combat(start, adapter.observe().decision)
    result = owner.choose(adapter.observe().decision)
    assert result.reason == 'belief_setup_unsupported' and result.simulations == 0
