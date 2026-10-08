"""Declared public setup -> persistent worlds -> ordinary engine conformance."""
from dataclasses import replace
import json

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.planning import (
    CombatStart, CombatEnd, StartingCard, StartingRelic, from_dict, to_dict,
)
from game.agent.headless import HeadlessAdapter
from game.agent.headless.full_projection import FullProjection
from game.agent.search.belief import CombatBelief, BeliefBudget
from game.agent.search.public_keys import action_key, public_key, end_key
from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.core.native_service import bind_combat
from game.headless.planning import UnsupportedSearch
from game.headless.run.construction import fork_combat
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.snapshots import restore_run


def setup(*, generator='infernal_blade', cards=DEFAULT_CARDS, hp=70, max_hp=80,
          deck=None, relics=None):
    return CombatStart('sts_declared_combat_start_v1', 'declared_fresh_inventory',
                       cards.snapshot_fingerprint(), 'ironclad', 0, 'overgrowth_vantom',
                       hp, max_hp, 0,
                       tuple(StartingCard(name, 0) for name in (deck or (generator, 'strike'))),
                       tuple(StartingRelic(name, count) for name, count in
                             (relics or (('nunchaku', 9), ('burning_blood', 0), ('blood_vial', 0)))),
                       (None, None, None))


def actual(start, *, cards=DEFAULT_CARDS, seed=5):
    """Independent ordinary setup path; not the planner's domain builder."""
    run = RunEngine(seed=seed, card_ids=[v.definition_id for v in start.deck],
                    hp=start.hp, max_hp=start.max_hp, gold=start.gold,
                    cards=cards, config=RunConfig(act='underdocks' if start.encounter_id.startswith('underdocks_')
                                                 else 'overgrowth'), rng_profile='native')
    for card, spec in zip(run.state.deck, start.deck):
        for _ in range(spec.upgrade_level):
            run.upgrade_card(card.instance_id)
    for relic in start.relics:
        run.obtain_relic(relic.definition_id)
        run.state.relics[-1] = replace(run.state.relics[-1], counter=relic.counter)
    from game.headless.run.inventory import add_potion
    run.state.potion_capacity = len(start.potions)
    run.state.potions = [None] * len(start.potions)
    for slot, name in enumerate(start.potions):
        if name is not None:
            add_potion(run.state, name, slot=slot)
    run.start_combat(encounter_id=start.encounter_id)
    return run, HeadlessAdapter(run, decision_profile='full_run_v2')


def hand(decision):
    return next(n.children for n in decision.context.children
                if n.kind == 'pile' and n.definition_id == 'hand')


def play(decision, definition):
    card = next(n for n in hand(decision) if n.definition_id == definition)
    return next(a for a in decision.candidates if a.kind == 'play_card' and a.subject == card.ref)


def advance(adapter, belief, action):
    frame = adapter.observe()
    report = adapter.step(frame.binding, action.ref)
    assert report.status == 'reconciled'
    summary = adapter.combat_summary
    if summary.completed:
        # The existing allowlisted producer supplies the settled public HUD and
        # inventory, including on defeat when observe() returns only RunOutcome.
        owner = FullProjection(adapter._engine, adapter._ids, adapter._history,
                               adapter._power_cards, 'attachment', adapter._epoch, False)
        successor = CombatEnd(summary.outcome, owner.run())
    else:
        successor = adapter.observe().decision
    result = belief.observe_transition(frame.decision, action, report, successor)
    assert result.reason is None, result
    if not isinstance(successor, CombatEnd):
        for seed in (11, 29):
            _, projected = belief.sample(seed)
            assert public_key(projected) == public_key(successor)
    return successor


def belief_for(start, *, cards=DEFAULT_CARDS, budget=BeliefBudget(2, 1024, 10)):
    run, adapter = actual(start, cards=cards)
    belief = CombatBelief(start, adapter.observe().decision, seed=41, budget=budget, cards=cards)
    return run, adapter, belief


def test_declaration_roundtrip_and_private_fields_or_missing_counters_rejected():
    value = to_dict(setup())
    assert from_dict(json.loads(json.dumps(value))) == setup()
    for private in ('seed', 'rng', 'snapshot', 'draw_order'):
        with pytest.raises(c.ContractError):
            from_dict({**value, private: 0})
    del value['relics'][0]['counter']
    with pytest.raises(c.ContractError):
        from_dict(value)
    value = to_dict(setup())
    value['relics'][0]['counter'] = True
    with pytest.raises(c.ContractError):
        from_dict(value)


@pytest.mark.parametrize('defer', [False, True])
def test_infernal_blade_cost_lifetime_reshuffle_and_persistent_nunchaku(defer):
    run, adapter, belief = belief_for(setup())
    opening = adapter.observe().decision
    assert opening.run.get('hp') == 72  # Blood Vial runs exactly once.
    after = advance(adapter, belief, play(opening, 'infernal_blade'))
    generated = next(card for card in hand(after) if card.definition_id != 'strike')
    assert generated.definition_id == 'rampage'  # Fixed actual fixture seed.
    assert generated.get('energy') == 0 and generated.get('free_this_turn') is True
    if defer:
        after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'end_turn'))
        generated = next(card for card in hand(after) if card.definition_id == 'rampage')
        assert generated.get('free_this_turn') is None
        assert generated.get('energy') == DEFAULT_CARDS.create('rampage').spec.cost
    energy = after.context.get('energy')
    cost = generated.get('energy')
    after = advance(adapter, belief, play(after, 'rampage'))
    relic = next(n for n in f.walk(after.run) if n.kind == 'relic' and n.definition_id == 'nunchaku')
    assert relic.get('display_counter') == 0
    assert after.context.get('energy') == energy - cost + 1
    assert next(r.counter for r in run.state.relics if r.definition_id == 'nunchaku') == 0
    after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'end_turn'))
    assert next(n for n in hand(after) if n.definition_id == 'rampage').get('free_this_turn') is None
    assert next(r.counter for r in run.state.relics if r.definition_id == 'nunchaku') == 0


def test_second_generator_composes_without_a_search_content_registration():
    _, adapter, belief = belief_for(setup(generator='jack_of_all_trades'))
    opening = adapter.observe().decision
    after = advance(adapter, belief, play(opening, 'jack_of_all_trades'))
    generated = [card for card in hand(after) if card.definition_id != 'strike']
    assert len(generated) == 1
    after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'end_turn'))
    assert generated[0].definition_id in {card.definition_id for card in hand(after)}


def test_branch_isolation_rng_aliases_and_existing_snapshot_roundtrip():
    run, adapter, belief = belief_for(setup())
    actual_before = run.snapshot()
    prior = [world._run.snapshot() for world in belief._worlds]
    world, public = belief.sample(713)
    same, same_public = belief.sample(713)
    assert public == same_public and world._run.snapshot() == same._run.snapshot()
    bind_combat(world._run.state.rng, world._run.combat)
    restored = restore_run(json.loads(json.dumps(world._run.snapshot())))
    assert restored.snapshot() == world._run.snapshot()
    world.step(public, action_key(public, play(public, 'infernal_blade')))
    assert [w._run.snapshot() for w in belief._worlds] == prior
    assert run.snapshot() == actual_before
    assert same._run.snapshot() == restored.snapshot()


def test_actual_private_rng_order_and_identifiers_never_enter_belief():
    start = setup(deck=('strike',) * 8 + ('infernal_blade',))
    run, adapter = actual(start)
    before = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.generation_rng.random()
    # Physical names change consistently, without changing any public facts.
    deck = run.combat.player.deck
    mapping = {card.instance_id: 'other.' + card.instance_id for card in deck.all_cards()}
    for card in deck.all_cards():
        card.instance_id = mapping[card.instance_id]
    deck._allocated_ids = {mapping[key] for key in deck._allocated_ids}
    deck.original_ids = {mapping[key] for key in deck.original_ids}
    after = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert public_key(before) == public_key(after)
    a = CombatBelief(start, before, seed=12, budget=BeliefBudget(2, 1024, 10))
    b = CombatBelief(start, after, seed=12, budget=BeliefBudget(2, 1024, 10))
    for seed in range(6):
        left, ld = a.sample(seed)
        right, rd = b.sample(seed)
        assert public_key(ld) == public_key(rd)
        assert left._run.snapshot() == right._run.snapshot()


def test_rejection_budget_never_reuses_a_stale_population():
    _, adapter, belief = belief_for(setup())
    belief.budget = BeliefBudget(2, 4, 10, replay_proposals=0)
    before = adapter.observe().decision
    action = play(before, 'strike')
    report = adapter.step(adapter.observe().binding, action.ref)
    successor = adapter.observe().decision
    fields = tuple(f.Field(v.key, v.value + 1) if v.key == 'gold' else v for v in successor.run.fields)
    inconsistent = replace(successor, run=replace(successor.run, fields=fields))
    result = belief.observe_transition(before, action, report, inconsistent)
    assert result.reason == 'belief_budget' and result.proposals == 4
    assert belief.current == inconsistent
    with pytest.raises(UnsupportedSearch, match='belief_budget'):
        belief.sample(1)


def test_pending_and_rejected_execution_are_not_applied_as_completed_actions():
    _, adapter, belief = belief_for(setup())
    before = adapter.observe().decision
    action = play(before, 'strike')
    rejected = c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', 'stale_decision')
    snapshots = [world._run.snapshot() for world in belief._worlds]
    result = belief.observe_transition(before, action, rejected, before)
    assert result.reason == 'rejected_no_mutation' and not belief.transitions
    assert [world._run.snapshot() for world in belief._worlds] == snapshots
    pending = c.ExecutionReport('sts_execution_report_v1', 'pending', 'queued', 'none')
    with pytest.raises(UnsupportedSearch, match='belief_unreconciled'):
        belief.observe_transition(before, action, pending, before)
    with pytest.raises(UnsupportedSearch, match='belief_unreconciled'):
        belief.sample(1)


def test_malformed_execution_receipt_invalidates_the_session():
    _, adapter, belief = belief_for(setup())
    before = adapter.observe().decision
    action = play(before, 'strike')
    invalid = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'none', 'none')
    with pytest.raises(UnsupportedSearch, match='belief_invalid_execution'):
        belief.observe_transition(before, action, invalid, before)
    with pytest.raises(UnsupportedSearch, match='belief_invalid_execution'):
        belief.sample(1)


def test_catalog_mismatch_and_incorrect_explicit_counter_fail():
    start = setup()
    _, adapter = actual(start)
    with pytest.raises(UnsupportedSearch, match='belief_catalog_mismatch'):
        CombatBelief(replace(start, card_catalog='different'), adapter.observe().decision)
    wrong = replace(start, relics=(replace(start.relics[0], counter=0), *start.relics[1:]))
    with pytest.raises(UnsupportedSearch, match='belief_budget'):
        CombatBelief(wrong, adapter.observe().decision, budget=BeliefBudget(1, 4, 10))


@pytest.mark.parametrize('invalid', ['missing_run', 'invalid_outcome', 'wrong_hp', 'duplicate_field'])
def test_malformed_completed_successor_invalidates_old_worlds(invalid):
    _, adapter, belief = belief_for(setup())
    before = adapter.observe().decision
    action = play(before, 'strike')
    report = adapter.step(adapter.observe().binding, action.ref)
    run = adapter.observe().decision.run
    if invalid == 'missing_run':
        end = CombatEnd('victory', None)
    elif invalid == 'invalid_outcome':
        end = CombatEnd('unfinished', run)
    elif invalid == 'wrong_hp':
        end = CombatEnd('defeat', run)
    else:
        end = CombatEnd('victory', replace(run, fields=(*run.fields, run.fields[0])))
    with pytest.raises(UnsupportedSearch, match='belief_boundary_unsupported'):
        belief.observe_transition(before, action, report, end)
    with pytest.raises(UnsupportedSearch, match='belief_boundary_unsupported'):
        belief.sample(1)


def test_missing_latent_draw_order_causes_bounded_deprivation_not_invented_state():
    from itertools import permutations
    from game.agent.search.world import SimulationWorld

    start = setup(deck=('strike',) * 6 + ('defend',) * 6)
    run, _, belief = belief_for(start)
    before = belief.current
    action = next(a for a in before.candidates if a.kind == 'end_turn')
    supported = set()
    for old in belief._worlds:
        branch = old.fork(2)
        supported.add(public_key(branch.step(branch.project(), action_key(before, action))))
    originals = list(run.combat.player.deck.draw_pile)
    # Choose a valid actual hidden ordering absent from the tiny particle set.
    # Only public observations from that actual game are sent to the belief.
    patterns = sorted(set(permutations(c.definition.definition_id for c in originals)))
    for pattern in patterns:
        pools = {name: iter([c for c in originals if c.definition.definition_id == name]) for name in set(pattern)}
        run.combat.player.deck.draw_pile[:] = [next(pools[name]) for name in pattern]
        oracle = SimulationWorld(fork_combat(run))
        predicted = oracle.step(oracle.project(), action_key(before, action))
        if public_key(predicted) not in supported:
            break
    else:
        pytest.fail('Fixture did not establish a missing latent order')
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    assert adapter.observe().decision == before
    report = adapter.step(adapter.observe().binding, action.ref)
    after = adapter.observe().decision
    belief.budget = BeliefBudget(2, 8, 10, replay_proposals=0)
    update = belief.observe_transition(before, action, report, after)
    assert update.reason == 'belief_budget' and update.survivors == 0
    assert adapter.combat_summary.outcome == 'ongoing'
    with pytest.raises(UnsupportedSearch, match='belief_budget'):
        belief.sample(1)


def test_terminal_cleanup_and_counter_persistence_match_ordinary_run():
    # A small deck keeps this a settlement check, independent of the later
    # milestone's population-replenishment support for long uncertain prefixes.
    start = setup(deck=('whirlwind',), relics=(('nunchaku', 9), ('burning_blood', 0), ('chemical_x', 0)))
    start = replace(start, deck=(StartingCard('whirlwind', 1),))
    run, adapter, belief = belief_for(start)
    current = adapter.observe().decision
    for _ in range(24):
        before = current
        action = next((a for a in current.candidates if a.kind == 'play_card'), None)
        action = action or next(a for a in current.candidates if a.kind == 'end_turn')
        current = advance(adapter, belief, action)
        if isinstance(current, CombatEnd):
            break
    assert isinstance(current, CombatEnd) and current.result == 'victory'
    assert run.combat is None
    assert current.run.get('hp') == adapter.combat_summary.hp == run.state.hp
    assert run.state.hp == min(run.state.max_hp, before.run.get('hp') + 6)
    assert all(end_key(world.completion) == end_key(current) for world in belief._worlds)
    assert all(world.terminal_value == pytest.approx(1 + .1 * run.state.hp / run.state.max_hp)
               for world in belief._worlds)


def test_generated_card_fight_completes_with_real_defeat_not_a_budget_loss():
    _, adapter, belief = belief_for(setup(hp=1, relics=(('nunchaku', 9), ('burning_blood', 0))))
    current = adapter.observe().decision
    current = advance(adapter, belief, play(current, 'infernal_blade'))
    current = advance(adapter, belief, play(current, 'rampage'))
    current = advance(adapter, belief, next(a for a in current.candidates if a.kind == 'end_turn'))
    assert isinstance(current, CombatEnd) and current.result == 'defeat'
    assert current.run.get('hp') == 0
    assert all(world.terminal_value == 0 for world in belief._worlds)
    assert all(end_key(world.completion) == end_key(current) for world in belief._worlds)


def test_small_generation_pool_has_engine_probabilities_and_fresh_future_samples():
    # Exact two-outcome fixture; production catalog exercised by tests above.
    names = {'rampage', 'twin_strike'}
    cards = CardCatalog(replace(d, generate_in_combat=d.definition_id in names)
                        for d in DEFAULT_CARDS.definitions)
    _, adapter, belief = belief_for(setup(cards=cards), cards=cards)
    opening = adapter.observe().decision
    action = play(opening, 'infernal_blade')
    counts = dict.fromkeys(names, 0)
    for seed in range(128):
        world, decision = belief.sample(seed)
        after = world.step(decision, action_key(opening, action))
        generated = next(card for card in hand(after) if card.definition_id != 'strike')
        counts[generated.definition_id] += 1
    assert sum(counts.values()) == 128
    assert all(40 <= count <= 88 for count in counts.values()), counts
