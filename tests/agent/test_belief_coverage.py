"""Declared Act 1 coverage: ordinary rules, room lifecycle and paused effects.

These are controlled inventories, not campaign attachments. Cases deliberately
exercise the production catalogs without a search-specific content registry.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from game.agent.contracts import full as f
from game.agent.contracts.planning import CombatEnd
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.belief import CombatBelief, BeliefBudget
from game.agent.search.public_keys import action_key, public_key, end_key
from game.agent.search.world import SimulationWorld
from game.agent.training.scenarios import Scenario
from game.headless.core.native_service import bind_combat
from game.headless.encounters.catalog import (ENCOUNTERS, NATIVE_OVERGROWTH_ENCOUNTERS,
                                               NATIVE_UNDERDOCKS_ENCOUNTERS)
from game.headless.planning import UnsupportedSearch
from game.headless.run.construction import declared_combat, fork_combat
from .test_belief import setup, actual, advance, play, hand
from .test_belief_search import end_turn
from .test_search import UniformPolicy


ACT1 = (*NATIVE_OVERGROWTH_ENCOUNTERS.values(), *NATIVE_UNDERDOCKS_ENCOUNTERS.values())
PANEL = ('overgrowth_nibbit', 'overgrowth_slimes', 'overgrowth_bygone_effigy', 'overgrowth_vantom',
         'underdocks_corpse_slugs_weak', 'underdocks_living_fog', 'underdocks_skulking_colony',
         'underdocks_lagavulin_matriarch')


@pytest.mark.parametrize('encounter', ACT1)
def test_all_registered_act1_declarations_match_independent_normal_setup(encounter):
    scenario = Scenario(encounter, 'controlled')
    start = scenario.planning_start()
    expected = scenario.make(17)
    proposed = declared_combat(deck=[(c.definition_id, c.upgrade_level) for c in start.deck],
        relics=[(r.definition_id, r.counter) for r in start.relics], potions=start.potions,
        hp=start.hp, max_hp=start.max_hp, gold=start.gold, encounter_id=encounter, seed=17)
    assert proposed.state.config.act == expected.state.config.act
    assert proposed.combat.player.rules.room_kind == ENCOUNTERS[encounter].room_kind
    assert public_key(SimulationWorld(proposed).project()) == public_key(SimulationWorld(expected).project())
    assert fork_combat(proposed).snapshot() == proposed.snapshot()


@pytest.mark.parametrize('encounter', PANEL)
def test_representative_rooms_search_and_every_advertised_root_branch(encounter):
    start = replace(setup(deck=('hemokinesis', 'defend'), relics=(('burning_blood', 0),)),
                    encounter_id=encounter, potions=('fire_potion', 'block_potion', None))
    run, adapter = actual(start)
    opening = adapter.observe().decision
    belief = CombatBelief(start, opening, seed=41, budget=BeliefBudget(2, 4096, 20))
    before = run.snapshot()
    # Enumerate even actions the checkpoint could mask or a small tree might
    # never visit: potions, every stable enemy target, cards, and end turn.
    for action in opening.candidates:
        world, public = belief.sample(27)
        after = world.step(public, action_key(opening, action))
        if after is None:
            assert isinstance(world.completion, CombatEnd)
        else:
            f.require_ready(after)
            assert public_key(world.fork(93).project()) == public_key(after)
    config = SearchConfig(model_version='public_belief_v1', simulations=8, max_depth=4,
                          time_limit=20, belief_particles=2, belief_proposals=4096, belief_seconds=15)
    owner = SearchPolicy(UniformPolicy(), config)
    owner.begin_combat(start, opening)
    result = owner.choose(opening)
    assert result.reason is None and result.simulations == 8
    assert result.action_ref in {a.ref for a in opening.candidates}
    assert sum(result.probabilities.values()) == pytest.approx(1)
    assert run.snapshot() == before
    after = advance(adapter, belief, end_turn(opening))
    assert after.context.get('round') == 2


def test_initial_relic_selector_has_a_declared_anchor_and_replays_setup_once():
    start = setup(deck=('strike', 'defend'), relics=(('gambling_chip', 0), ('pendulum', 2)))
    run, adapter = actual(start)
    opening = adapter.observe().decision
    assert run.combat.player.rules.selection
    belief = CombatBelief(start, opening, seed=11, budget=BeliefBudget(2, 128, 10))
    after = advance(adapter, belief, next(a for a in opening.candidates if a.kind == 'select_card'))
    after = advance(adapter, belief, next(a for a in after.candidates if a.kind == 'confirm_selection'))
    assert not run.combat.player.rules.selection
    assert after.context.get('round') == 1
    assert next(r.counter for r in run.state.relics if r.definition_id == 'pendulum') == 0
    assert belief.recover().reason is None


def test_reactive_selection_preserves_captured_enemy_hit_and_future_streams():
    # Terror Eel's second move is a three-hit attack. Centennial Puzzle fires
    # on its first unblocked hit; Stratagem exposes its ordinary draw selector.
    start = replace(setup(deck=('stratagem', 'defend', 'defend'),
                          relics=(('centennial_puzzle', 0), ('anchor', 0)), hp=80),
                    encounter_id='underdocks_terror_eel')
    run, adapter = actual(start)
    belief = CombatBelief(start, adapter.observe().decision, seed=4, budget=BeliefBudget(2, 512, 10))
    current = advance(adapter, belief, play(belief.current, 'stratagem'))
    # Block the first attack in full, so Puzzle remains available on turn two.
    for _ in range(2):
        current = advance(adapter, belief, play(current, 'defend'))
    current = advance(adapter, belief, end_turn(current))
    while run.combat.player.rules.selection:
        action = next((a for a in current.candidates if a.kind == 'confirm_selection'), current.candidates[0])
        current = advance(adapter, belief, action)
    current = advance(adapter, belief, end_turn(current))
    progress = deepcopy(run.combat.player.rules.enemy_turn)
    assert progress and progress['move']['hit'] == 1
    assert progress['move']['intent']['attack_count'] == 3
    hp = run.combat.player.hp
    prior = [w._run.snapshot() for w in belief._worlds]
    for seed in (7, 23):
        world, public = belief.sample(seed)
        assert world._run.combat.player.rules.enemy_turn == progress
        bind_combat(world._run.state.rng, world._run.combat)
        while world._run.combat.player.rules.selection:
            action = next((a for a in public.candidates if a.kind == 'confirm_selection'), public.candidates[0])
            public = world.step(public, action_key(public, action))
        assert world._run.combat.turn == 3
        assert world._run.combat.player.hp == hp - 6  # Two remaining hits, exactly once.
    assert prior == [w._run.snapshot() for w in belief._worlds]
    assert run.combat.player.hp == hp and run.combat.player.rules.enemy_turn == progress


def test_invalid_paused_task_cannot_be_forked_as_a_valid_decision():
    start = setup(deck=('strike', 'defend'), relics=(('gambling_chip', 0),))
    run, _ = actual(start)
    run.combat.player.rules.tasks.append(['not_an_engine_task'])
    with pytest.raises(ValueError):
        fork_combat(run, future_seed=7)


def test_unresolved_duplicate_draw_references_are_idempotent_until_public_progress():
    from game.agent.headless.identity import Identities
    ids = Identities()
    first, second = ('combat', 0, 'private.a'), ('combat', 0, 'private.b')
    ids.ref('card', first)
    ids.ref('card', second)
    # Both names were previously visible. A shuffle puts them back, in an
    # order that must not affect a repeated read or a pending selection toggle.
    hidden = [(second, 'defend'), (first, 'defend')]
    ids.reconcile_draw([], hidden, lambda value: value)
    references = dict(ids.refs)
    ids.reconcile_draw([], hidden, lambda value: value)
    ids.reconcile_draw([], list(reversed(hidden)), lambda value: value)
    assert ids.refs == references
    # Once one copy is drawn, use public destination order again. The old
    # private association must not reveal which indistinguishable copy it was.
    ids.reconcile_draw([(second, 'defend')], [(first, 'defend')], lambda value: value)
    assert ids.ref('card', second) == 'card:0'
    assert ids.ref('card', first) == 'card:1'


def test_summoned_enemy_slots_and_smog_survive_filtering_and_branching():
    start = replace(setup(deck=('defend',), relics=(('burning_blood', 0),)),
                    encounter_id='underdocks_living_fog')
    run, adapter = actual(start)
    belief = CombatBelief(start, adapter.observe().decision, seed=1, budget=BeliefBudget(2, 64, 10))
    current = advance(adapter, belief, end_turn(belief.current))
    current = advance(adapter, belief, end_turn(current))
    assert [type(e).__name__ for e in run.combat.enemies] == ['LivingFog', 'GasBomb']
    assert [e.get('slot') for n in current.context.children if n.kind == 'enemies' for e in n.children] == [0, 1]
    assert any(n.definition_id == 'smoggy' for n in f.walk(current.context))
    current = advance(adapter, belief, play(current, 'defend'))
    assert any(n.kind == 'card' and n.get('smog') is True for n in f.walk(current.context))
    current = advance(adapter, belief, end_turn(current))
    assert hand(current)[0].get('smog') is None  # The engine expires the affliction at turn end.
    assert not run.combat.enemies[1].is_alive
    assert belief.recover().reason is None


@pytest.mark.parametrize('encounter', ['overgrowth_nibbit', 'overgrowth_bygone_effigy', 'overgrowth_vantom',
                                      'underdocks_sewer_clam', 'underdocks_terror_eel', 'underdocks_soul_fysh'])
def test_room_sensitive_entry_and_real_defeat_settlement(encounter):
    # Room-sensitive relics make the ordinary/elite/boss distinction observable.
    start = replace(setup(deck=('defend',), hp=1, relics=(('sling_of_courage', 0), ('pantograph', 0))),
                    encounter_id=encounter)
    run, adapter = actual(start)
    belief = CombatBelief(start, adapter.observe().decision, seed=3, budget=BeliefBudget(1, 1024, 10))
    kind = ENCOUNTERS[encounter].room_kind
    assert run.combat.player.hp == (26 if kind == 'boss' else 1)
    assert run.combat.player.strength == (2 if kind == 'elite' else 0)
    for _ in range(16):
        current = advance(adapter, belief, end_turn(belief.current))
        if isinstance(current, CombatEnd):
            break
    assert current.result == 'defeat' and current.run.get('hp') == 0
    assert all(end_key(w.completion) == end_key(current) and w.terminal_value == 0 for w in belief._worlds)


def test_fishing_rod_counter_and_upgrade_settle_only_after_ordinary_victory():
    start = replace(setup(deck=('bludgeon',), hp=70,
                          relics=(('burning_blood', 0), ('fishing_rod', 2), ('akabeko', 0))),
                    encounter_id='underdocks_seapunk_weak')
    run, adapter = actual(start)
    belief = CombatBelief(start, adapter.observe().decision, seed=9, budget=BeliefBudget(2, 512, 10))
    for _ in range(8):
        current = belief.current
        attack = next((a for a in current.candidates if a.kind == 'play_card'), None)
        current = advance(adapter, belief, attack or end_turn(current))
        if isinstance(current, CombatEnd):
            break
    assert current.result == 'victory'
    assert run.state.deck[0].upgrade_level == 1
    assert next(r.counter for r in run.state.relics if r.definition_id == 'fishing_rod') == 0
    assert all(end_key(w.completion) == end_key(current) for w in belief._worlds)


@pytest.mark.parametrize('encounter', ['dense_vegetation_event', 'hive_chomper', 'missing'])
def test_unsupported_encounter_is_named_without_silent_default_region(encounter):
    start = setup(deck=('strike',))
    _, adapter = actual(start)
    with pytest.raises(UnsupportedSearch, match='belief_encounter_unsupported'):
        CombatBelief(replace(start, encounter_id=encounter), adapter.observe().decision)


def test_multiple_enemy_search_is_invariant_to_actual_private_state():
    start = replace(setup(deck=('hemokinesis', 'defend', 'defend', 'defend', 'defend', 'defend'),
                          relics=(('burning_blood', 0),)), encounter_id='underdocks_corpse_slugs_weak')
    run, adapter = actual(start)
    opening = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.niche_rng.random()
    from game.agent.headless import HeadlessAdapter
    equivalent = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert public_key(opening) == public_key(equivalent)
    config = SearchConfig(model_version='public_belief_v1', simulations=8, max_depth=4, time_limit=20,
                          belief_particles=1, belief_proposals=4096, belief_seconds=15)
    results = []
    for public in (opening, equivalent):
        owner = SearchPolicy(UniformPolicy(), config)
        owner.begin_combat(start, public)
        result = owner.choose(public)
        assert result.reason is None
        results.append((result.action_ref, result.probabilities, result.values, result.visits))
    assert results[0] == results[1]
