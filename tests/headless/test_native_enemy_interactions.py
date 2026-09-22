"""Native enemy-turn work completes before a delayed Horn replay answer."""

from copy import deepcopy
from dataclasses import asdict
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
from game.headless.powers.ironclad import apply_power
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_enemy_interactions_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    construction = MonsterConstruction(streams['monster_ai'], streams['niche'])
    combat = CombatEngine(
        cards=DEFAULT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [DEFAULT_CARDS.create('strike' if row['scenario']=='block' and i==0 else 'defend') for i in range(row['fillers'])],
        encounter_factory=lambda _: [Chomper(construction), Chomper(construction)],
    )
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    combat.reset(relics=[RelicInstance('the_abacus', 'relic.0'), RelicInstance('gremlin_horn', 'relic.1')])
    combat.cards_per_turn = 5
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: int(c.instance_id.rsplit('.',1)[1]))
    identities = {c.instance_id: f'card.{i}' for i, c in enumerate(cards)}
    p.deck.draw_pile, p.deck.discard_pile = [], cards
    if row['scenario']=='block':
        p.deck.draw_pile,p.deck.discard_pile=list(reversed(cards)),[]
        apply_power(p,'hellraiser',1)
        combat.enemies[1].block=10
    else:
        relic=RelicInstance('fiddle','relic.2')
        p.rules.relics.append(asdict(relic))
        p.rules.relic_data[relic.instance_id]={}
    p.deck.rng.setstate(shuffle_start)
    p.energy = 0
    apply_power(p, 'thorns', 1)
    apply_power(p, 'stratagem', 1)
    if row['withTools']:
        apply_power(p, 'tools_of_the_trade', 1)
    combat.enemies[0].hp = 1
    for enemy in combat.enemies:
        enemy.statuses._counts.clear()  # Native fixture omits AfterAddedToRoom.

    return combat, identities


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r: f'{r["scenario"]}-{r["seed"]}-{r["fillers"]}-{r["answerLast"]}-{r["withTools"]}')
def test_native_enemy_turn_and_next_hand_precede_horn_choice(row, monkeypatch):
    combat, identities = prepare(row)
    p = combat.player

    def state(engine):
        p = engine.player
        return dict(hand=[identities[c.instance_id] for c in p.hand],
                    draw=[identities[c.instance_id] for c in reversed(p.deck.draw_pile)],
                    discard=[identities[c.instance_id] for c in p.deck.discard_pile],
                    energy=p.energy, block=p.block, hp=p.hp,
                    side='Player' if p.rules.player_side else 'Enemy', turn=engine.turn)

    def enemies(engine):
        return [dict(slot='enemy' if i == 0 else 'second', hp=e.hp, maxHp=e.max_hp, block=e.block,
                     move='CLAMP_MOVE' if e.intent.move_name == 'Clamp' else 'SCREECH_MOVE')
                for i, e in enumerate(engine.enemies) if e.is_alive]

    # Native fixture enters directly at the prepared enemy side; Python uses
    # EndTurn with an empty hand, which has the same incoming piles/resources.
    assert {**state(combat), 'side': 'Enemy'} == row['before']
    assert enemies(combat) == row['enemiesBefore']
    hits = []
    original_enemy_damage = Enemy.take_damage
    original_player_damage = type(p).take_damage

    def enemy_damage(enemy, amount, **kwargs):
        hp, block = enemy.hp, enemy.block
        entry=dict(slot='enemy' if enemy is combat.enemies[0] else 'second')
        hits.append(entry)  # Native records damage before dispatching death hooks.
        result = original_enemy_damage(enemy, amount, **kwargs)
        entry.update(damage=hp-enemy.hp, blocked=block-enemy.block)
        return result

    def player_damage(player, amount, **kwargs):
        hp = player.hp
        result = original_player_damage(player, amount, **kwargs)
        # Native current-hit damage is 8; Abacus can grant block within Thorns.
        hits.append(dict(slot='player', damage=hp-player.hp, blocked=amount-(hp-player.hp)))
        return result

    monkeypatch.setattr(Enemy, 'take_damage', enemy_damage)
    monkeypatch.setattr(type(p), 'take_damage', player_damage)
    combat.apply(EndTurn())
    assert hits == row['hits']
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
    assert len(combat.enemies) == 2 and not combat.enemies[0].is_alive
    assert not p.rules.tasks and not p.rules.deferred_hooks and not p.rules.active_hook
    for engine in (combat, other):
        deck = engine.player.deck
        for stream, native in [(deck.rng, 'shuffle'), (deck.target_rng, 'targets'), (deck.niche_rng, 'niche'), (engine.rng, 'ai')]:
            assert stream.counter == row[native]['counter']
            assert deepcopy(stream).next_double() == row[native]['suffix']
