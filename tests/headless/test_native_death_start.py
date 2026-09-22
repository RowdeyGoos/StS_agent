"""Native simultaneous death choices and poison side-start work with JSON replay."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.base import Enemy
from game.headless.monsters.hive_normal import Chomper
from game.headless.monsters.phrog_parasite import PhrogParasite, Wriggler
from game.headless.powers.ironclad import apply_power
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_death_start_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    construction = MonsterConstruction(streams['monster_ai'], streams['niche'])
    combat = CombatEngine(
        cards=DEFAULT_CARDS, cards_per_turn=0, player_max_hp=500,
        deck_factory=lambda: [DEFAULT_CARDS.create('strike' if row['scenario']=='multiple' and i<3 else 'defend') for i in range(row['fillers'])],
        encounter_factory=lambda _: [(PhrogParasite if row['scenario']=='spawn' else Chomper)(construction)] + [Chomper(construction) for _ in range(5 if row['scenario']=='multiple' else 1)],
    )
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    combat.reset(relics=[RelicInstance('the_abacus', 'relic.0'), RelicInstance('gremlin_horn', 'relic.1')])
    combat.cards_per_turn = 5
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: int(c.instance_id.rsplit('.',1)[1]))
    identities = {c.instance_id: f'card.{i}' for i, c in enumerate(cards)}
    p.deck.draw_pile, p.deck.discard_pile = [], cards
    p.deck.rng.setstate(shuffle_start)
    p.energy = 0
    p.hp = p.max_hp = 500
    apply_power(p, 'thorns', 1)
    apply_power(p, 'stratagem', 1)
    if row['withTools']:
        apply_power(p, 'tools_of_the_trade', 1)
    combat.enemies[0].hp = 1
    for enemy in combat.enemies:
        enemy.statuses._counts.clear()  # Native fixture omits AfterAddedToRoom.

    if row['scenario']=='multiple':
        apply_power(p,'hellraiser',1)
        for enemy in combat.enemies[:-1]:
            enemy.hp=1
        combat.enemies[-1].hp=combat.enemies[-1].max_hp=500
    else:
        combat.enemies[0].statuses.add('poison',1)
        if row['scenario']=='accelerant':
            combat.enemies[0].hp=3
            combat.enemies[0].statuses.add('poison',2)
            combat.enemies[1].statuses.add('poison',4)
            apply_power(p,'accelerant',2)
        if row['scenario']=='spawn':
            combat.enemies[0].statuses.add('infested',4)
    return combat, identities


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r: f'{r["scenario"]}-{r["seed"]}-{r["fillers"]}-{r["answerLast"]}-{r["withTools"]}')
def test_native_death_choices_and_side_start_reactions(row, monkeypatch):
    combat, identities = prepare(row)
    p = combat.player

    def state(engine):
        p = engine.player
        return dict(hand=[identities[c.instance_id] for c in p.hand],
                    draw=[identities[c.instance_id] for c in reversed(p.deck.draw_pile)],
                    discard=[identities[c.instance_id] for c in p.deck.discard_pile],
                    energy=p.energy, block=p.block, hp=p.hp,
                    side='Player' if p.rules.player_side else 'Enemy', turn=engine.turn)

    def slot(engine,enemy):
        i=engine.enemies.index(enemy)
        if isinstance(enemy,Wriggler):
            return f'wriggler{i-1}'
        return 'enemy' if i==0 else 'second' if i==1 else f'extra.{i}'

    def enemies(engine):
        moves={'Clamp':'CLAMP_MOVE','Screech':'SCREECH_MOVE','Infect':'INFECT_MOVE',
               'Spawned':'SPAWNED_MOVE','Bite':'NASTY_BITE_MOVE','Wriggle':'WRIGGLE_MOVE'}
        return [dict(slot=slot(engine,e),hp=e.hp,maxHp=e.max_hp,block=e.block,type=type(e).__name__,
                     poison=e.statuses.get('poison'),move=moves[e.intent.move_name])
                for e in engine.enemies if e.is_alive]

    # Native fixture enters directly at the prepared enemy side; Python uses
    # EndTurn with an empty hand, which has the same incoming piles/resources.
    assert {**state(combat), 'side': 'Enemy'} == row['before']
    assert enemies(combat) == row['enemiesBefore']
    hits = []
    original_enemy_damage = Enemy.take_damage
    original_player_damage = type(p).take_damage

    def enemy_damage(enemy, amount, **kwargs):
        if enemy not in combat.enemies:
            return original_enemy_damage(enemy,amount,**kwargs)
        hp, block = enemy.hp, enemy.block
        entry=dict(slot=slot(combat,enemy))
        hits.append(entry)  # Native records damage before dispatching death hooks.
        result = original_enemy_damage(enemy, amount, **kwargs)
        entry.update(damage=hp-enemy.hp, blocked=block-enemy.block)
        return result

    def player_damage(player, amount, **kwargs):
        if player is not p:
            return original_player_damage(player,amount,**kwargs)
        hp = player.hp
        result = original_player_damage(player, amount, **kwargs)
        # Native current-hit damage is 8; Abacus can grant block within Thorns.
        hits.append(dict(slot='player', damage=hp-player.hp, blocked=amount-(hp-player.hp)))
        return result

    original_unblockable=Enemy.take_unblockable_damage
    def unblockable(enemy,amount):
        if enemy not in combat.enemies:
            return original_unblockable(enemy,amount)
        hp=enemy.hp
        entry=dict(slot=slot(combat,enemy),blocked=0)
        hits.append(entry)
        result=original_unblockable(enemy,amount)
        entry['damage']=hp-enemy.hp
        return result
    monkeypatch.setattr(Enemy,'take_unblockable_damage',unblockable)
    monkeypatch.setattr(Enemy, 'take_damage', enemy_damage)
    monkeypatch.setattr(type(p), 'take_damage', player_damage)
    result=combat.apply(EndTurn())
    assert len(result.details['enemy_actions'])==row['moves']
    assert enemies(combat) == row['enemiesCheckpoint']
    assert p.rules.enemy_turn is None and not p._defer_death_hooks
    answers = [a for a in row['answers'] if a['options']]
    assert bool(p.rules.selection) == bool(answers)
    # Empty live Horn choices automatically settle before the next decision.
    assert state(combat) == (answers[0]['state'] if answers else row['after'])
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)
    for answer in answers:
        assert state(combat) == answer['state']
        assert enemies(combat) == answer['enemies']
        assert [identities[i] for i in p.rules.selection['candidates']] == answer['options']
        assert p.rules.selection['source'] == ('stratagem' if answer['pile'] == 'DrawPile' else 'tools_of_the_trade')
        selected = next(i for i, label in identities.items() if label == answer['selected'][0])
        for action in (ChooseCombatCard(selected), ConfirmCombatSelection()):
            combat.apply(action)
            other.apply(action)
            assert saved(combat) == saved(other)
        # Every exposed boundary, including activation of the second context.
        other.restore(saved(combat))
    assert state(combat) == row['after']
    assert enemies(combat) == row['enemiesAfter']
    assert not combat.enemies[0].is_alive
    assert hits==row['hits']
    assert not p.rules.tasks and not p.rules.deferred_hooks and not p.rules.active_hook
    for engine in (combat, other):
        deck = engine.player.deck
        for stream, native in [(deck.rng, 'shuffle'), (deck.target_rng, 'targets'), (deck.niche_rng, 'niche'), (engine.rng, 'ai')]:
            assert stream.counter == row[native]['counter']
            assert deepcopy(stream).next_double() == row[native]['suffix']


def multiple_choices():
    row=next(r for r in RECORD['result']['rows'] if r['scenario']=='multiple' and r['fillers']==3 and not r['withTools'])
    combat,_=prepare(row)
    combat.apply(EndTurn())
    assert combat.player.rules.selection and len(combat.player.rules.deferred_hooks)==2
    return combat


def test_native_matrix_exercises_two_horns_and_live_singleton_then_empty_choice():
    rows=[r for r in RECORD['result']['rows'] if r['scenario']=='multiple' and r['fillers']==3]
    assert rows and all(r['pendingSources'].count('GremlinHorn')>=2 for r in rows)
    assert any([len(a['options']) for a in r['answers'][:3]]==[3,1,0] for r in rows)
    assert any(any(a['listener']=='ToolsOfTheTradePower' for a in r['answers']) for r in RECORD['result']['rows'])


@pytest.mark.parametrize('mutation',['duplicate_context','already_selected','foreign_candidate','invalid_draw'])
def test_multiple_waiting_choices_reject_corrupt_restore_atomically(mutation):
    combat=multiple_choices()
    before=saved(combat)
    bad=deepcopy(before)
    rules=bad['player']['rules']
    waiting=rules['deferred_hooks'][0]
    if mutation=='duplicate_context':
        waiting['context']=rules['active_hook']
    elif mutation=='already_selected':
        waiting['selection']['selected']=waiting['selection']['candidates'][:1]
    elif mutation=='foreign_candidate':
        waiting['selection']['candidates'].append('not-owned')
    else:
        next(t for t in waiting['tasks'] if t[0]=='draw_after_shuffle')[1]=-1
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before


@pytest.mark.parametrize('winner',['player','enemy'])
def test_explicit_terminal_disposal_cancels_all_waiting_death_and_setup_work(winner):
    # Explicit synthetic disposal boundary, not a legal command while selecting
    # or a native full EndCombat fixture.
    combat=multiple_choices()
    p=combat.player
    piles_before=[[c.instance_id for c in getattr(p.deck,n)] for n in ('hand','draw_pile','discard_pile')]
    rng_before=[deepcopy(r.getstate()) for r in (p.deck.rng,p.deck.target_rng,p.deck.niche_rng,combat.rng)]
    if winner=='player':
        for enemy in combat.enemies:
            enemy.hp=0
    else:
        p.hp=0
    from game.headless.core.hook_scheduler import cancel_terminal_work
    cancel_terminal_work(p)
    combat.resolve_external_effect()
    assert combat.done and combat.winner==winner
    assert not p.rules.tasks and not p.rules.deferred_hooks and not p.rules.active_hook
    assert p.rules.selection is None and not p.rules.pending_events
    assert combat.legal_actions()==()
    assert [[c.instance_id for c in getattr(p.deck,n)] for n in ('hand','draw_pile','discard_pile')]==piles_before
    assert [r.getstate() for r in (p.deck.rng,p.deck.target_rng,p.deck.niche_rng,combat.rng)]==rng_before
    other=CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other)==saved(combat)
