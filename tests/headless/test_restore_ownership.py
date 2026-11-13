"""A restored engine owns its mutable state.

Restoring one snapshot twice gives independent engines, and neither shares a
mutable container with that snapshot. The engine edits card cost bookkeeping and
relic data in place, and searches restore the same snapshot many times.
"""
from copy import deepcopy
import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.card_state import CardState
from game.headless.core.snapshots import card_record, restore_card
from game.headless.enchantments.base import enchant
from game.headless.map.graph import MapGraph, MapNode
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run import events
from game.headless.run.actions import (ChooseEventOption, ChooseNode, ChooseRelicCard, ConfirmRelicSelection,
                                       ContinueAct, LeaveEvent)
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.snapshots import restore_run
from game.headless.run.state import RunPhase


def card(run, name):
    return next(c for c in run.combat.player.deck.all_cards() if c.definition.definition_id == name)


def play(run, name):
    identity = card(run, name).instance_id
    run.apply(next(a for a in run.legal_actions() if isinstance(a, PlayCard) and a.instance_id == identity))


def plain(value):
    return json.loads(json.dumps(value))


def branches(run, form='detached'):
    """Two engines restored from one snapshot, that snapshot, and an untouched copy of it.

    `form`: the default detached snapshot, one with shared content tables, or stored JSON."""
    snapshot = run.snapshot(shared_content=form == 'shared_content')
    if form == 'json':
        snapshot = plain(snapshot)
    return (restore_run(snapshot, cards=run.cards), restore_run(snapshot, cards=run.cards),
            snapshot, deepcopy(snapshot))


def scribble(value):
    """Change every mutable container of plain nested data in place, including the empty ones."""
    for child in list(value.values() if isinstance(value, dict) else value):
        if isinstance(child, (dict, list, tuple)):
            scribble(child)
    if isinstance(value, dict):
        value['scribble'] = True
    elif isinstance(value, list):
        value.append('scribble')


def scribble_state(snapshot):
    # The content tables may be the shared read-only ones; everything else is state.
    for key in ('state', 'graph', 'combat'):
        if snapshot[key] is not None:
            scribble(snapshot[key])


def cost_fight():
    """Second turn: Bookmark has discounted the retained Bludgeon, and Enlightenment is in hand."""
    run = RunEngine(seed=3, config=RunConfig(), card_ids=('bludgeon', 'enlightenment'))
    enchant(run.state.deck[0], 'steady')
    add_relic(run.state, 'bookmark', cards=run.cards)
    add_potion(run.state, 'fire_potion')
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    run.apply(EndTurn())
    assert card(run, 'bludgeon').combat_state.until_played_discount == 1
    return run


def chest_run():
    graph = MapGraph((MapNode('chest0', 'treasure', ('chest1',)), MapNode('chest1', 'treasure', ())), 'chest0')
    run = RunEngine(seed=2, graph=graph)
    add_relic(run.state, 'silver_crucible', cards=run.cards)
    return run


def event_fight():
    """An event combat keeps its suspended event as a nested continuation record."""
    run = RunEngine(config=RunConfig(), gold=1000)
    run.state.act_index = 1
    events.begin(run.state, 'battleworn_dummy', cards=run.cards)
    run.apply(ChooseEventOption(run.state.pending['event_instance_id'], 'setting_2'))
    assert run.combat is not None and run.state.event_combats[-1].continuation is not None
    return run


def stored_cards_run():
    """Pael's Tooth keeps the cards it removed as records inside its relic data."""
    run = RunEngine(rng_profile='native')
    run.obtain_relic('paels_tooth')
    while run.state.relic_work:
        actions = run.legal_actions()
        run.apply(next((a for a in actions if isinstance(a, ConfirmRelicSelection)), None)
                  or next(a for a in actions if isinstance(a, ChooseRelicCard)
                          and a.instance_id not in run.state.relic_work[0]['selected']))
    tooth = run.state.relics[-1]
    assert tooth.definition_id == 'paels_tooth' and len(tooth.data['cards']) == 5
    return run


def journey(run, steps):
    """Each decision state of a demo route: map, rooms, rewards, combats and the act change."""
    for _ in range(steps):
        yield run
        if run.combat is not None:
            for enemy in tuple(run.combat.enemies):
                if enemy.is_alive and not getattr(enemy, 'about_to_blow', False):
                    enemy.take_damage(10000, is_attack=False)
            run.combat.resolve_external_effect()
            if run.combat.done:
                run.finish_combat()
            else:
                run.apply(EndTurn())
        elif run.state.phase is RunPhase.ACT_COMPLETE:
            run.apply(ContinueAct())
        else:
            actions = run.legal_actions()
            run.apply(next((a for a in actions if isinstance(a, LeaveEvent)), None)
                      or choose_demo_action(run, rest_choice='rest', path='left'))


def test_restored_card_owns_every_container_of_its_state():
    source = DEFAULT_CARDS.create('bash', instance_id='run.card.0')
    source.combat_state = CardState(turn_cost_override=1, combat_cost_override=2, until_played_discount=1,
                                    cost_override_order=['combat', 'turn'], cost_discount_baselines={'turn': 1},
                                    played_cost_baselines=[0, -1, 0])
    record = card_record(source)
    pristine = deepcopy(record)
    first, second = restore_card(record), restore_card(record)
    # Read from the dataclass, so a container field added later is covered too.
    containers = [name for name, value in vars(CardState()).items() if isinstance(value, (list, dict, set))]
    assert len(containers) >= 3
    for name in containers:
        owned = getattr(first.combat_state, name)
        assert owned == record['combat_state'][name] and owned is not record['combat_state'][name]
        assert owned is not getattr(second.combat_state, name)
        owned.clear()
    assert record == pristine and card_record(second) == pristine


def test_cost_setting_command_in_one_restore_leaves_its_sibling_and_the_snapshot_unchanged():
    acting, sibling, snapshot, pristine = branches(cost_fight())
    play(acting, 'enlightenment')
    state = card(acting, 'bludgeon').combat_state
    assert state.cost_override_order == ['turn'] and state.cost_discount_baselines == {'turn': 1}
    assert snapshot == pristine
    assert sibling.snapshot() == pristine
    play(sibling, 'enlightenment')
    assert sibling.snapshot() == acting.snapshot()


def test_playing_a_card_in_one_restore_does_not_change_its_cost_in_a_sibling():
    run = cost_fight()
    play(run, 'enlightenment')
    assert run.combat.player.card_cost(card(run, 'bludgeon')) == 1  # Set to 1 after a discount of 1.
    acting, sibling, snapshot, pristine = branches(run)
    # Finishing a play clears that card's discount baselines in place. Shared, that
    # would make the unplayed copy cost 1 - 1 = 0 in every other restore.
    play(acting, 'bludgeon')
    player = sibling.combat.player
    assert player.card_cost(card(sibling, 'bludgeon')) == 1
    energy = player.energy
    play(sibling, 'bludgeon')
    assert energy - player.energy == 1
    assert snapshot == pristine
    assert sibling.snapshot() == acting.snapshot()


def test_room_command_in_one_restore_leaves_relic_data_of_its_sibling_and_the_snapshot_unchanged():
    acting, sibling, snapshot, pristine = branches(chest_run())
    # Silver Crucible counts entered chests in its own data; only the first chest is empty.
    acting.apply(ChooseNode('chest0'))
    crucible = next(r for r in acting.state.relics if r.definition_id == 'silver_crucible')
    assert crucible.data == {'treasures': 1} and acting.state.pending['stage'] == 'empty'
    assert snapshot == pristine
    assert sibling.snapshot() == pristine
    sibling.apply(ChooseNode('chest0'))
    assert sibling.snapshot() == acting.snapshot()


@pytest.mark.parametrize('build,read,record', (
    (stored_cards_run, lambda e: e.state.relics[-1].data, lambda s: s['state']['relics'][-1]['data']),
    (event_fight, lambda e: e.state.event_combats[-1].continuation,
     lambda s: s['state']['event_combats'][-1]['continuation']),
), ids=('relic_data', 'event_continuation'))
def test_restored_nested_records_are_copies(build, read, record):
    first, second, snapshot, pristine = branches(build())
    assert read(first) == record(snapshot) and read(first) is not record(snapshot)
    assert read(first) is not read(second)
    scribble(read(first))
    assert snapshot == pristine and second.snapshot() == pristine


@pytest.mark.parametrize('build', (cost_fight, chest_run, event_fight, stored_cards_run))
@pytest.mark.parametrize('form', ('detached', 'shared_content', 'json'))
def test_changing_a_snapshot_after_restore_cannot_change_the_engine(build, form):
    run = build()
    engine, _, snapshot, pristine = branches(run, form)
    scribble_state(snapshot)
    assert plain(engine.snapshot()) == plain(pristine) == plain(run.snapshot())
    assert engine.legal_actions() == run.legal_actions()


@pytest.mark.parametrize('character', ('ironclad', 'silent', 'regent', 'necrobinder', 'defect'))
def test_every_decision_state_of_a_route_restores_without_sharing_its_snapshot(character):
    # Ironclad plays a whole act and continues into the next one; the others add their own combat state.
    whole = character == 'ironclad'
    run = (RunEngine.ironclad_run(last_act='hive', seed=2) if whole
           else RunEngine.campaign(character=character, seed=23))
    run.state.max_hp = run.state.hp = 10000
    kinds = set()
    for state in journey(run, 110 if whole else 40):
        kinds.add('combat' if state.combat else (state.state.pending or {}).get('kind', state.state.phase.value))
        engine, _, snapshot, pristine = branches(state)
        scribble_state(snapshot)
        assert engine.snapshot() == pristine
    assert {'route', 'combat', 'reward'} <= kinds
    assert not whole or 'act_complete' in kinds and run.state.completed_acts
