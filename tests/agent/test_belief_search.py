"""Maintained public beliefs, prefix recovery and the existing search owner."""
from dataclasses import replace
from itertools import permutations
from collections import Counter

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd
from game.agent.headless import HeadlessAdapter
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.belief import CombatBelief, BeliefBudget
from game.agent.search.public_keys import action_key, public_key
from game.agent.search.world import SimulationWorld
from game.headless.planning import UnsupportedSearch
from game.headless.run.construction import fork_combat
from .test_belief import setup, actual, belief_for, advance, hand, play
from .test_search import UniformPolicy


def end_turn(decision):
    return next(a for a in decision.candidates if a.kind == 'end_turn')


def observe(adapter, owner, action):
    frame = adapter.observe()
    report = adapter.step(frame.binding, action.ref)
    successor = adapter.combat_completion or adapter.observe().decision
    owner.observe_transition(frame.decision, action, report, successor)
    return successor


def test_collapse_recovers_missing_order_by_replaying_all_public_boundaries():
    start = setup(deck=('strike',) * 4 + ('defend',) * 4)
    run, _, belief = belief_for(start)
    before = belief.current
    action = end_turn(before)
    supported = set()
    for old in belief._worlds:
        branch = old.fork(2)
        supported.add(public_key(branch.step(branch.project(), action_key(before, action))))
    originals = list(run.combat.player.deck.draw_pile)
    for order in permutations(originals):
        run.combat.player.deck.draw_pile[:] = order
        oracle = SimulationWorld(fork_combat(run))
        predicted = oracle.step(oracle.project(), action_key(before, action))
        if public_key(predicted) not in supported:
            break
    else:
        pytest.fail('Fixture must include an absent but possible hidden ordering')
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    assert adapter.observe().decision == before
    belief.budget = BeliefBudget(2, 4, 15, replay_proposals=8192)
    after = observe(adapter, belief, action)
    assert belief.last_update.recovered and belief.reason is None, belief.last_update
    assert belief.last_update.replay_steps > 0
    assert len(belief.transitions) == 1
    assert public_key(belief.sample(6)[1]) == public_key(after)


def test_budget_fallback_retains_new_progress_and_recovers_later():
    _, adapter, belief = belief_for(setup(deck=('strike', 'defend')))
    belief._invalidate('belief_budget')
    belief.budget = BeliefBudget(2, 2, 10, replay_proposals=0)
    before = belief.current
    after = observe(adapter, belief, play(before, 'strike'))
    assert belief.reason == 'belief_budget' and len(belief.transitions) == 1
    after = observe(adapter, belief, end_turn(after))
    assert belief.reason == 'belief_budget' and len(belief.transitions) == 2
    belief.budget = BeliefBudget(2, 16, 10, replay_proposals=128)
    recovered = belief.recover()
    assert recovered.recovered and recovered.reason is None
    assert public_key(belief.sample(29)[1]) == public_key(after)


def test_replay_cannot_skip_a_contradicted_intermediate_observation():
    _, adapter, belief = belief_for(setup(deck=('strike', 'defend')))
    belief.budget = BeliefBudget(2, 2, 10, replay_proposals=0)
    before = belief.current
    action = play(before, 'strike')
    report = adapter.step(adapter.observe().binding, action.ref)
    after = adapter.observe().decision
    wrong = replace(after, run=replace(after.run, fields=tuple(
        f.Field(v.key, v.value + 1) if v.key == 'gold' else v for v in after.run.fields)))
    belief.observe_transition(before, action, report, wrong)
    report = adapter.step(adapter.observe().binding, end_turn(after).ref)
    successor = adapter.observe().decision
    belief.observe_transition(wrong, end_turn(wrong), report, successor)
    belief.budget = BeliefBudget(2, 4, 10, replay_proposals=32)
    update = belief.recover()
    assert update.reason == 'belief_budget'
    assert update.proposals == update.replay_proposals == 32
    with pytest.raises(UnsupportedSearch, match='belief_budget'):
        belief.sample(1)


def test_known_top_placement_survives_unrelated_action_recovery_draw_and_reshuffle():
    _, adapter, belief = belief_for(setup(deck=('strike', 'headbutt', 'pommel_strike', 'defend'),
                                           relics=(('nunchaku', 9),)))
    current = advance(adapter, belief, play(belief.current, 'strike'))
    current = advance(adapter, belief, play(current, 'headbutt'))
    current = advance(adapter, belief, play(current, 'defend'))
    belief.budget = BeliefBudget(2, 8, 10, replay_proposals=2048)
    assert belief.recover().reason is None
    for seed in range(10):
        world, public = belief.sample(seed)
        assert world._run.combat.player.deck.draw_pile[-1].definition.definition_id == 'strike'
    # End turn consumes the placement, then refills from the discard using the
    # engine shuffle. No history helper contains a Headbutt-specific branch.
    current = advance(adapter, belief, end_turn(current))
    assert hand(current)[0].definition_id == 'strike'
    assert belief.recover().reason is None


def test_card_selector_keeps_pending_parent_and_executes_effect_once():
    start = setup(deck=('burning_pact', 'strike', 'defend'))
    _, adapter, belief = belief_for(start)
    after = advance(adapter, belief, play(belief.current, 'burning_pact'))
    assert any(n.kind == 'selection' for n in after.context.children)
    for seed in (11, 29):
        world, public = belief.sample(seed)
        assert public_key(public) == public_key(after)
        assert world._run.combat.player.pending_play is not None or world._run.combat.player.rules.selection
    assert belief.recover().reason is None
    selected = next(a for a in after.candidates if a.kind == 'select_card')
    after = advance(adapter, belief, selected)
    assert not any(n.kind == 'selection' for n in after.context.children)
    assert len(belief.transitions) == 2
    exhaust = next(n for n in after.context.children if n.kind == 'pile' and n.definition_id == 'exhaust')
    assert len(exhaust.children) == 1


def test_generated_potion_options_are_materialized_across_forks_and_selection():
    # Tiny synthetic generation catalog keeps complete prefix rejection bounded.
    from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
    cards = CardCatalog(replace(d, generate_in_combat=d.definition_id in {'strike', 'twin_strike', 'rampage'})
                        for d in DEFAULT_CARDS.definitions)
    start = replace(setup(deck=('strike',), cards=cards), potions=('attack_potion', None, None))
    run, adapter = actual(start, cards=cards)
    belief = CombatBelief(start, adapter.observe().decision, cards=cards, seed=41,
                          budget=BeliefBudget(2, 1024, 10))
    before = belief.current
    after = advance(adapter, belief, next(a for a in before.candidates if a.kind == 'use_potion'))
    snapshots = [w._run.snapshot() for w in belief._worlds]
    for seed in range(6):
        world, public = belief.sample(seed)
        assert public_key(public) == public_key(after)
        assert world._run.combat.player.rules.selection
        assert world._run.combat.player.rules.potion_uses
    assert snapshots == [w._run.snapshot() for w in belief._worlds]
    assert belief.recover().reason is None
    after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'select_card'))
    after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'confirm_selection'))
    assert not any(n.kind == 'selection' for n in after.context.children)
    assert run.state.potions[0] is None
    assert len(hand(after)) == 2


def test_weighted_parent_sampling_and_duplicate_draw_posterior_match_enumeration():
    # Enumerate the six physical orders of two identical Strikes and one Defend.
    # Drawing Strike has probability 2/3; conditional on that draw, either card
    # is equally likely to be next. No hypothetical identity becomes evidence.
    start = setup(deck=('pommel_strike',) + ('strike',) * 4 + ('defend',) * 3)
    for seed in range(30):
        run, adapter = actual(start, seed=seed)
        draw = run.combat.player.deck.draw_pile
        if Counter(c.definition.definition_id for c in draw) == {'strike': 2, 'defend': 1} and any(
                n.definition_id == 'pommel_strike' for n in hand(adapter.observe().decision)):
            break
    else:
        pytest.fail('No enumerated fixture')
    before = adapter.observe().decision
    belief = CombatBelief(start, before, seed=1, budget=BeliefBudget(1, 8192, 20))
    source = belief._worlds[0]
    ids = [c.instance_id for c in source._run.combat.player.deck.draw_pile]
    worlds = []
    for order in permutations(ids):
        world = source.fork(7)
        pool = {c.instance_id: c for c in world._run.combat.player.deck.draw_pile}
        world._run.combat.player.deck.draw_pile[:] = [pool[i] for i in order]
        worlds.append(world)
    belief._worlds, belief.weights = worlds, (1/6,) * 6
    draws = Counter()
    key = action_key(before, play(before, 'pommel_strike'))
    for seed in range(180):
        world, public = belief.sample(seed)
        after = world.step(public, key)
        draws[hand(after)[-1].definition_id] += 1
    assert 100 <= draws['strike'] <= 140, draws
    matching = []
    for world in worlds:
        branch = world.fork(8)
        after = branch.step(branch.project(), key)
        if hand(after)[-1].definition_id == 'strike':
            matching.append(after)
    assert len(matching) == 4
    belief.budget = BeliefBudget(128, 1024, 20, replay_proposals=0)
    report = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
    result = belief.observe_transition(before, play(before, 'pommel_strike'), report, matching[0])
    assert result.reason is None
    next_cards = Counter(w._run.combat.player.deck.draw_pile[-1].definition.definition_id for w in belief._worlds)
    assert 40 <= next_cards['strike'] <= 88, next_cards
    # A weighted posterior is used directly, without applying its likelihood twice.
    belief.weights = (1.,) + (0.,) * (len(belief._worlds) - 1)
    first = belief._worlds[0]._run.combat.player.deck.draw_pile[-1].definition.definition_id
    assert all(belief.sample(seed)[0]._run.combat.player.deck.draw_pile[-1].definition.definition_id == first
               for seed in range(12))


def test_search_model_versions_identity_legality_hidden_invariance_and_reset():
    start = setup(deck=('strike',) * 6 + ('defend',) * 2)
    run, adapter = actual(start)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.player.deck.generation_rng.random()
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert public_key(first) == public_key(second)
    config = SearchConfig(model_version='public_belief_v1', simulations=16, time_limit=20,
                          belief_particles=2, belief_seconds=10, seed=7)
    a, b = SearchPolicy(UniformPolicy(), config), SearchPolicy(UniformPolicy(), config)
    assert a.identity != SearchPolicy(UniformPolicy(), replace(config, model_version='reconstruction_v1')).identity
    snapshot = run.snapshot()
    a.begin_combat(start, first)
    b.begin_combat(start, second)
    left, right = a.choose(first), b.choose(second)
    assert left.reason is right.reason is None
    assert (left.action_ref, left.values, left.probabilities, left.visits) == (
        right.action_ref, right.values, right.probabilities, right.visits)
    assert left.simulations == 16 and sum(left.probabilities.values()) == pytest.approx(1)
    assert run.snapshot() == snapshot
    assert a(first) in first.candidates
    with pytest.raises(ValueError, match='Reset'):
        a.begin_combat(start, first)
    a.reset()
    assert a.choose(first).reason == 'missing_planning_anchor'


def test_search_follows_pending_selector_and_retains_every_reconciled_result():
    start = setup(deck=('burning_pact', 'strike', 'defend'))
    _, adapter = actual(start)
    policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version='public_belief_v1',
        simulations=8, time_limit=20, belief_particles=2))
    policy.begin_combat(start, adapter.observe().decision)
    before = adapter.observe().decision
    assert policy.choose(before).reason is None
    after = observe(adapter, policy, play(before, 'burning_pact'))
    assert policy.choose(after).reason is None
    chosen = next(a for a in after.candidates if a.kind == 'select_card')
    after = observe(adapter, policy, chosen)
    assert len(policy.reconciled_results) == 2
    assert policy.choose(after).reason in (None, 'forced_action')


def test_replay_deadline_step_and_journal_limits_do_not_fabricate_terminal_results():
    _, adapter, belief = belief_for(setup(deck=('strike', 'defend')))
    after = advance(adapter, belief, play(belief.current, 'strike'))
    belief.budget = BeliefBudget(2, 4, 10, replay_proposals=4, replay_steps=0)
    assert belief.recover().reason == 'belief_budget'
    assert belief.last_update.replay_steps == 0
    assert belief.recover(seconds=0).proposals == 0
    belief.budget = BeliefBudget(2, 4, 10, history_limit=1)
    with pytest.raises(UnsupportedSearch, match='belief_history_budget'):
        observe(adapter, belief, end_turn(after))
    assert adapter.combat_summary.outcome == 'ongoing'
    assert not isinstance(belief.current, CombatEnd)


def test_initial_search_works_when_collapse_replay_is_disabled():
    start = setup(deck=('strike', 'defend'))
    _, adapter = actual(start)
    policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version='public_belief_v1',
        simulations=4, time_limit=20, belief_particles=2, belief_replay_proposals=0))
    policy.begin_combat(start, adapter.observe().decision)
    result = policy.choose(adapter.observe().decision)
    assert result.reason is None and result.simulations == 4
    assert policy.belief.last_update.replay_proposals == 0


def test_end_turn_retention_selector_is_searchable_and_resumes_once():
    start = setup(deck=('well_laid_plans', 'strike', 'defend'))
    run, adapter = actual(start)
    policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version='public_belief_v1',
        simulations=4, time_limit=20, belief_particles=2))
    policy.begin_combat(start, adapter.observe().decision)
    policy.choose(adapter.observe().decision)
    after = observe(adapter, policy, play(adapter.observe().decision, 'well_laid_plans'))
    policy.choose(after)
    after = observe(adapter, policy, end_turn(after))
    assert run.combat.player.rules.turn_ending and run.combat.player.rules.selection
    snapshot = run.snapshot()
    result = policy.choose(after)
    assert result.reason is None and result.simulations == 4
    assert policy(after) in after.candidates
    assert run.snapshot() == snapshot
    after = observe(adapter, policy, next(a for a in after.candidates if a.kind == 'select_card'))
    after = observe(adapter, policy, next(a for a in after.candidates if a.kind == 'confirm_selection'))
    assert after.context.get('round') == 2
    assert not run.combat.player.rules.turn_ending
    assert run.combat.player.rules.selection is None
    assert policy.belief.reason is None


def test_exhausted_thinking_budget_journals_progress_before_later_recovery():
    start = setup(deck=('strike', 'defend'))
    _, adapter = actual(start)
    policy = SearchPolicy(UniformPolicy(), SearchConfig(model_version='public_belief_v1',
        simulations=4, time_limit=20, belief_particles=2))
    policy.begin_combat(start, adapter.observe().decision)
    before = adapter.observe().decision
    policy.choose(before)
    policy.last_result = replace(policy.last_result, seconds=policy.config.time_limit)
    after = observe(adapter, policy, play(before, 'strike'))
    assert policy.belief.last_update.proposals == 0
    assert policy.belief.reason == 'belief_budget' and policy.belief.current == after
    assert policy.choose(after).reason in (None, 'forced_action')


def test_public_completion_is_frozen_at_cleanup_not_reprojected_from_later_state():
    run, adapter = actual(setup(deck=('defend',), hp=1, relics=(('burning_blood', 0),)))
    assert adapter.combat_completion is None
    frame = adapter.observe()
    adapter.step(frame.binding, end_turn(frame.decision).ref)
    completion = adapter.combat_completion
    assert completion.result == 'defeat' and completion.run.get('hp') == 0
    # No future inventory/state read may alter the already verified public fact.
    run.state.gold += 10
    assert adapter.combat_completion is completion
    assert completion.run.get('gold') == 0
