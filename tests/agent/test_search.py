"""Public-only search conformance, stochastic branches and useful decisions."""
from dataclasses import replace
from random import Random
from types import SimpleNamespace

import pytest

from game.agent.headless import HeadlessAdapter
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.model import PublicCombatModel, SearchHistory, action_key, observation_key
from game.agent.training.rewards import RewardSpec
from game.headless.monsters.vantom import Vantom
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.planning import UnsupportedSearch


class UniformPolicy:
    reward_spec = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})
    identity = 'controlled_uniform_v1'
    model = SimpleNamespace(action_policy='all_legal_v1')

    def probabilities(self, decision):
        return {a.ref: 1 / len(decision.candidates) for a in decision.candidates}, .5


def fixture(cards=('strike', 'defend', 'pommel_strike', 'bash', 'anger', 'defend'), *, hp=40, enemy_hp=173):
    run = RunEngine(seed=1, card_ids=cards, hp=hp, config=RunConfig(), rng_profile='native')
    run.obtain_relic('burning_blood')
    run.start_combat(encounter_factory=lambda rng: [Vantom(rng)])
    run.combat.enemies[0].hp = enemy_hp
    return run, HeadlessAdapter(run, decision_profile='full_run_v2')


def reconcile(adapter, history, action):
    before = adapter.observe().decision
    report = adapter.step(adapter.observe().binding, action.ref)
    successor = adapter.observe()
    after = getattr(successor, 'decision', successor)
    history.observe(before, action, report, after)
    return after


def test_lethal_search_cleanup_and_no_actual_mutation():
    run, adapter = fixture(('strike', 'defend'), enemy_hp=1)
    decision = adapter.observe().decision
    snapshot = run.snapshot()
    policy = SearchPolicy(UniformPolicy(), SearchConfig(simulations=16, time_limit=20))
    result = policy.choose(decision)
    assert result.reason is None, result
    chosen = next(a for a in decision.candidates if a.ref == result.action_ref)
    assert chosen.kind == 'play_card'
    assert next(n for n in decision.context.children if n.kind == 'pile' and n.definition_id == 'hand').children
    model = PublicCombatModel(decision, SearchHistory())
    world, public = model.sample(10)
    assert world.step(public, action_key(decision, chosen)) is None
    assert world.terminal_value == pytest.approx(1 + .1 * 46 / 80)
    assert run.snapshot() == snapshot
    assert sum(result.probabilities.values()) == pytest.approx(1)
    assert result.simulations == 16


def test_hidden_rng_and_draw_order_do_not_change_search():
    run, adapter = fixture(('strike', 'defend') * 5)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert observation_key(first) == observation_key(second)
    config = SearchConfig(simulations=16, time_limit=20, seed=12, exploration=True)
    a = SearchPolicy(UniformPolicy(), config).choose(first)
    b = SearchPolicy(UniformPolicy(), config).choose(second)
    assert (a.action_ref, a.probabilities, a.values, a.visits) == (b.action_ref, b.probabilities, b.values, b.visits)


def test_multiturn_matches_real_engine_with_public_history():
    run, adapter = fixture(('strike', 'defend'))
    history = SearchHistory()
    for turn in range(5):
        decision = adapter.observe().decision
        model = PublicCombatModel(decision, history)
        world, public = model.sample(8)
        chosen = next(a for a in decision.candidates if a.kind == 'end_turn')
        predicted = world.step(public, action_key(decision, chosen))
        successor = reconcile(adapter, history, chosen)
        if predicted is None:
            break
        assert observation_key(predicted) == observation_key(successor)
    assert run.combat is None or run.combat.enemies[0].strength == 2


def test_unknown_order_sampling_is_not_canonical_order():
    run, adapter = fixture(('strike', 'defend', 'bash', 'anger', 'pommel_strike', 'shrug_it_off'))
    p = run.combat.player
    p.deck.draw_pile.extend(p.hand)
    p.hand.clear()
    # This controlled all-draw observation exercises only the sampling law.
    decision = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    model = PublicCombatModel(decision, SearchHistory())
    tops = set()
    for seed in range(24):
        world, _ = model.sample(seed)
        tops.add(world._run.combat.player.deck.draw_pile[-1].definition.definition_id)
    assert len(tops) >= 5


def test_missing_history_and_known_placement_sources_fall_back():
    run, adapter = fixture()
    action = next(a for a in adapter.observe().decision.candidates if a.kind == 'end_turn')
    adapter.step(adapter.observe().binding, action.ref)
    policy = SearchPolicy(UniformPolicy())
    assert policy.choose(adapter.observe().decision).reason == 'missing_opening_history'
    run, adapter = fixture(('strike', 'havoc'))
    result = SearchPolicy(UniformPolicy()).choose(adapter.observe().decision)
    assert result.reason == 'card:havoc'
    assert result.action_ref in {a.ref for a in adapter.observe().decision.candidates}


def test_objective_mismatch_is_not_reinterpreted():
    policy = UniformPolicy()
    policy.reward_spec = RewardSpec.full_run()
    with pytest.raises(ValueError, match='unshaped combat'):
        SearchPolicy(policy)
    policy.reward_spec = UniformPolicy.reward_spec
    policy.manifest = {'algorithm': 'ppo', 'learner_config': {'ppo': {'gamma': .99}}}
    with pytest.raises(ValueError, match='undiscounted'):
        SearchPolicy(policy)


def test_small_odd_budget_keeps_both_finalists_in_contention():
    _, adapter = fixture(('strike',))
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=9, max_depth=1, time_limit=20)).choose(
        adapter.observe().decision)
    assert result.reason is None
    assert sorted(result.visits.values()) == [4, 5]


@pytest.mark.parametrize('kwargs', [{'simulations': 0}, {'time_limit': float('nan')}, {'max_depth': True}])
def test_invalid_budgets(kwargs):
    with pytest.raises(ValueError):
        SearchConfig(**kwargs)


def card_action(decision, name):
    from game.agent.contracts import full as f
    refs = {n.ref for n in f.walk(decision.context) if n.kind == 'card' and n.definition_id == name}
    return next(a for a in decision.candidates if a.kind == 'play_card' and a.subject in refs)


def test_supported_catalog_entries_exist():
    from game.headless.planning import CARDS, POTIONS, RELICS
    run, _ = fixture()
    for name in CARDS:
        run.cards.definition(name)
    from game.headless.potions.base import POTIONS as potion_catalog
    from game.headless.relics.base import RELICS as relic_catalog
    assert POTIONS <= potion_catalog.keys()
    assert RELICS <= relic_catalog.keys()


@pytest.mark.parametrize('relic', ['golden_pearl', 'nutritious_oyster', 'neows_talisman'])
def test_completed_neow_pickups_preserve_public_successors_and_cleanup(relic):
    run = RunEngine(seed=1, card_ids=('strike',), hp=40, config=RunConfig(), rng_profile='native')
    run.obtain_relic('burning_blood')
    run.obtain_relic(relic)
    run.start_combat(encounter_factory=lambda rng: [Vantom(rng)])
    run.combat.enemies[0].hp = 1
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    history = SearchHistory()
    decision = adapter.observe().decision
    world, public = PublicCombatModel(decision, history).sample(2)
    end = next(a for a in decision.candidates if a.kind == 'end_turn')
    predicted = world.step(public, action_key(decision, end))
    actual = reconcile(adapter, history, end)
    assert observation_key(predicted) == observation_key(actual)
    world, public = PublicCombatModel(actual, history).sample(3)
    strike = card_action(actual, 'strike')
    assert world.step(public, action_key(actual, strike)) is None
    reconcile(adapter, history, strike)
    assert world.terminal_value == pytest.approx(1 + .1 * run.state.hp / run.state.max_hp)


def test_forced_opening_still_records_public_history():
    run, adapter = fixture(('wound', 'wound'))
    policy = SearchPolicy(UniformPolicy(), SearchConfig(simulations=4))
    before = adapter.observe().decision
    result = policy.choose(before)
    assert result.reason == 'forced_action'
    chosen = next(a for a in before.candidates if a.ref == result.action_ref)
    report = adapter.step(adapter.observe().binding, chosen.ref)
    after = adapter.observe().decision
    policy.observe_transition(before, chosen, report, after)
    PublicCombatModel(after, policy.history)
    assert len(policy.history.transitions) == 1


def test_dead_enemy_keeps_slot_without_ambiguous_phase():
    from game.headless.monsters.overgrowth import Nibbit
    run = RunEngine(seed=1, card_ids=('strike', 'defend'), rng_profile='native')
    run.start_combat(encounter_factory=lambda _: [Nibbit(Random(2), role='front'), Nibbit(Random(2), role='back')])
    run.combat.enemies[0].hp = 1
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    decision = adapter.observe().decision
    history = SearchHistory()
    history.attach(decision)
    successor = reconcile(adapter, history, card_action(decision, 'strike'))
    model = PublicCombatModel(successor, history)
    world, public = model.sample(4)
    assert observation_key(public) == observation_key(successor)
    assert not world._run.combat.enemies[0].is_alive
    assert len(world._run.combat.enemies) == 2


def test_draw_and_reshuffle_use_existing_rules():
    run, adapter = fixture(('pommel_strike', 'defend', 'strike'))
    history = SearchHistory()
    decision = adapter.observe().decision
    history.attach(decision)
    # Spend two cards so Pommel must reshuffle the known discard multiset.
    decision = reconcile(adapter, history, card_action(decision, 'strike'))
    decision = reconcile(adapter, history, card_action(decision, 'defend'))
    model = PublicCombatModel(decision, history)
    counts = {'strike': 0, 'defend': 0}
    for seed in range(128):
        world, public = model.sample(seed)
        successor = world.step(public, action_key(decision, card_action(decision, 'pommel_strike')))
        hand = next(n for n in successor.context.children if n.definition_id == 'hand')
        assert len(hand.children) == 1
        counts[hand.children[0].definition_id] += 1
    assert all(40 < n < 88 for n in counts.values())
    assert run.combat.player.deck.discard_pile  # Real world was never advanced.


def test_pending_exhaust_replay_has_exact_counter_and_successor():
    run, adapter = fixture(('burning_pact', 'strike', 'defend'))
    history = SearchHistory()
    decision = adapter.observe().decision
    history.attach(decision)
    decision = reconcile(adapter, history, card_action(decision, 'burning_pact'))
    model = PublicCombatModel(decision, history)
    world, public = model.sample(2)
    assert world._run.combat.player.cards_played_this_turn == run.combat.player.cards_played_this_turn == 1
    chosen = next(a for a in decision.candidates if a.kind == 'select_card')
    predicted = world.step(public, action_key(decision, chosen))
    actual = reconcile(adapter, history, chosen)
    assert observation_key(predicted) == observation_key(actual)


def test_power_and_potion_are_simulated_through_cleanup():
    run, _ = fixture(('inflame', 'strike'), enemy_hp=1)
    # Combat potion mirror must be populated by combat initialization.
    from game.headless.potions.base import PotionInstance
    run.state.potions[0] = PotionInstance('fire_potion', f'run.item.{run.state.next_item_id}')
    run.state.next_item_id += 1
    from dataclasses import asdict
    run.combat.player.rules.potions = [asdict(p) if p else None for p in run.state.potions]
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    decision = adapter.observe().decision
    history = SearchHistory()
    history.attach(decision)
    decision = reconcile(adapter, history, card_action(decision, 'inflame'))
    model = PublicCombatModel(decision, history)
    world, public = model.sample(2)
    assert world._run.combat.player.strength == run.combat.player.strength == 2
    potion = next(a for a in decision.candidates if a.kind == 'use_potion')
    assert world.step(public, action_key(decision, potion)) is None
    assert world.terminal_value > 1
    assert run.combat is not None


def test_tiny_stochastic_targets_match_enumerated_outcomes():
    from itertools import product
    from game.headless.monsters.overgrowth import Nibbit
    run = RunEngine(seed=1, card_ids=('sword_boomerang',), rng_profile='native')
    run.start_combat(encounter_factory=lambda _: [Nibbit(Random(2)), Nibbit(Random(3))])
    decision = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    model = PublicCombatModel(decision, SearchHistory())
    damage = []
    for outcomes in product((0, 1), repeat=3):
        world, public = model.sample(2)
        choices = iter(outcomes)
        world._run.combat.player.deck.target_rng = SimpleNamespace(choice=lambda values: values[next(choices)])
        start = world._run.combat.enemies[0].hp
        world.step(public, action_key(decision, card_action(decision, 'sword_boomerang')))
        damage.append(start - world._run.combat.enemies[0].hp)
    assert sorted(damage) == [0, 3, 3, 3, 6, 6, 6, 9]
    assert sum(damage) / 8 == 4.5


def test_time_budget_returns_an_advertised_fallback():
    _, adapter = fixture()
    decision = adapter.observe().decision
    result = SearchPolicy(UniformPolicy(), SearchConfig(time_limit=1e-12)).choose(decision)
    assert result.reason == 'no_completed_simulation'
    assert result.cutoff == 'search_time_budget'
    assert result.action_ref in {a.ref for a in decision.candidates}
    assert result.simulations == 0


def test_known_top_survives_duplicate_anonymity_until_drawn():
    run, adapter = fixture(('strike', 'headbutt', 'pommel_strike', 'defend', 'strike', 'strike'))
    # Controlled hand, with indistinguishable Strikes still in the hidden pile.
    p = run.combat.player
    cards = p.deck.all_cards()
    p.hand[:] = [next(c for c in cards if c.definition.definition_id == n) for n in ('strike', 'headbutt', 'pommel_strike')]
    p.deck.draw_pile[:] = [c for c in cards if c not in p.hand]
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    history = SearchHistory()
    decision = adapter.observe().decision
    history.attach(decision)
    decision = reconcile(adapter, history, card_action(decision, 'strike'))
    decision = reconcile(adapter, history, card_action(decision, 'headbutt'))
    model = PublicCombatModel(decision, history)
    assert len(model.facts['known_top']) == 1
    for seed in range(12):
        world, public = model.sample(seed)
        predicted = world.step(public, action_key(decision, card_action(decision, 'pommel_strike')))
        hand = next(n for n in predicted.context.children if n.definition_id == 'hand')
        assert [n.definition_id for n in hand.children] == ['strike']
    actual = reconcile(adapter, history, card_action(decision, 'pommel_strike'))
    assert not PublicCombatModel(actual, history).facts['known_top']


def test_known_top_and_bottom_are_not_shuffled():
    from game.headless.planning import reconstruct
    from game.agent.search.model import facts_from
    run, _ = fixture(('strike', 'defend', 'bash', 'anger', 'pommel_strike', 'shrug_it_off'))
    p = run.combat.player
    p.deck.draw_pile.extend(p.hand)
    p.hand.clear()
    decision = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    history = SearchHistory()
    history.attach(decision)
    facts = facts_from(decision, history)
    facts['known_top'] = [facts['piles']['draw_pile'][0]['ref']]
    facts['known_bottom'] = [facts['piles']['draw_pile'][1]['ref']]
    for seed in range(8):
        world, refs = reconstruct(facts, seed=seed, enemy_phases=(0,))
        draw = world.combat.player.deck.draw_pile
        assert draw[-1].instance_id == refs[facts['known_top'][0]][1]
        assert draw[0].instance_id == refs[facts['known_bottom'][0]][1]


@pytest.mark.parametrize('monster', ['Seapunk', 'SludgeSpinner'])
def test_underdocks_transitions_and_observed_debuffs(monster):
    from game.headless.monsters import underdocks_normal
    run = RunEngine(seed=2, card_ids=('defend',), max_hp=500, rng_profile='native')
    run.start_combat(enemy_factory=lambda: getattr(underdocks_normal, monster)(Random(2)))
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    history = SearchHistory()
    for _ in range(6):
        decision = adapter.observe().decision
        model = PublicCombatModel(decision, history)
        world, public = model.sample(9)
        assert observation_key(public) == observation_key(decision)
        end = next(a for a in decision.candidates if a.kind == 'end_turn')
        predicted = world.step(public, action_key(decision, end))
        actual = reconcile(adapter, history, end)
        # Random next intent may differ; all current-move effects must agree.
        assert (predicted.context.get('hp'), predicted.context.get('strength')) == (actual.context.get('hp'), actual.context.get('strength'))
        assert world._run.combat.player.statuses.as_dict() == run.combat.player.statuses.as_dict()


def test_lethal_ordering_and_blocking_survival():
    _, adapter = fixture(('strike', 'bash'), enemy_hp=16)
    decision = adapter.observe().decision
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=64, time_limit=20)).choose(decision)
    assert result.action_ref == card_action(decision, 'bash').ref
    _, adapter = fixture(('defend', 'defend'), hp=4)
    decision = adapter.observe().decision
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=32, time_limit=20)).choose(decision)
    assert next(a for a in decision.candidates if a.ref == result.action_ref).kind == 'play_card'


def test_synthetic_world_can_be_serialized_and_branched():
    from game.headless.run.snapshots import restore_run
    _, adapter = fixture()
    model = PublicCombatModel(adapter.observe().decision, SearchHistory())
    world, public = model.sample(2)
    snapshot = world._run.snapshot()
    clone = restore_run(snapshot)
    assert clone.snapshot() == snapshot
    # RNG alias ownership survives the engine's ordinary snapshot contract.
    assert clone.combat.enemies[0].rng is clone.combat.rng
    assert clone.combat.player.deck.rng is clone.state.rng.stream('shuffle')


def test_private_identity_renaming_does_not_change_public_search():
    from game.headless.run.snapshots import restore_run
    run, adapter = fixture(('strike', 'defend') * 5)
    first = adapter.observe().decision
    mapping = {c.instance_id: f'run.card.{100+i}' for i, c in enumerate(run.state.deck)}
    mapping.update({r.instance_id: f'run.item.{200+i}' for i, r in enumerate(run.state.relics)})
    def rename(value):
        if isinstance(value, dict):
            return {mapping.get(k, k): rename(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rename(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    snapshot = rename(run.snapshot())
    snapshot['state']['next_card_id'] += 100
    snapshot['state']['next_item_id'] += 200
    second = HeadlessAdapter(restore_run(snapshot), decision_profile='full_run_v2').observe().decision
    assert observation_key(first) == observation_key(second)
    config = SearchConfig(simulations=16, time_limit=20, seed=99)
    a, b = (SearchPolicy(UniformPolicy(), config).choose(d) for d in (first, second))
    assert (a.action_ref, a.probabilities, a.values, a.visits) == (b.action_ref, b.probabilities, b.values, b.visits)
