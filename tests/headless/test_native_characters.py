"""Eight native starter callback probes, including all twelve exclusive potions."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from game.headless.characters import CHARACTERS, STARTER_UPGRADES
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.relics.base import RelicInstance
from game.headless.potions.base import PotionInstance
from game.headless.potions import use as potion_use
from game.headless.relics.character_hooks import start, hook
from game.headless.core.resolution import drain
from tests.headless.test_native_item_status import saved, slug, power_map

ROOT=Path(__file__).parents[2]
RECORD=json.loads(gzip.decompress((ROOT/'docs/evidence/native_characters_2026_09_20.json.gz').read_bytes()))
ROWS=[r for r in RECORD['result']['rows'] if r['scenario'].startswith('focused_character_')]


def state(engine, draw):
    p=engine.player;r=p.rules
    return dict(hp=p.hp,draw=draw,stars=r.stars,
        osty=None if r.osty is None else dict(hp=r.osty['hp'],maxHp=r.osty['max_hp']),
        slots=r.orb_slots,orbs=[r.orbs[i]['kind'].title()+'Orb' for i in r.orb_order],
        powers=power_map(engine),enemyPowers=power_map(engine,enemy=True),
        cards=[dict(pile=label,id=c.definition.definition_id.upper(),upgraded=c.upgraded)
               for label,pile in [('Hand',p.hand),('DrawPile',reversed(p.deck.draw_pile)),('DiscardPile',p.deck.discard_pile)] for c in pile])


def apply(engine, step, character):
    if step['kind']=='next_start':
        p=engine.player; p.rules.round_number+=1
        start(p,p.rules.relics[0],5)
        hook(p,p.rules.relics[0],'after_side_start','');drain(p)
    else:
        items=[None if r is None else PotionInstance(**r) for r in engine.player.rules.potions]
        owner=SimpleNamespace(state=SimpleNamespace(potions=items),combat=engine)
        name=slug(step['kind']);item=next(i for i in items if i and i.definition_id==name)
        action=next(a for a in potion_use.actions(owner) if a.instance_id==item.instance_id)
        potion_use.use(owner,action)


@pytest.mark.parametrize('row',ROWS,ids=lambda r:r['scenario'])
def test_native_character_start_and_exclusive_potion_continuations(row):
    name=row['character'].lower();definition=CHARACTERS[name];refined=row['scenario'].endswith('_refined')
    assert (definition.max_hp,definition.relic,definition.deck)==(row['hp'],row['starter'].lower(),tuple(n.lower() for n in row['deck']))
    assert row['gold']==99
    service=NativeRandomService(2)
    engine=CombatEngine(cards=DEFAULT_CARDS,deck_factory=lambda:[],cards_per_turn=0,player_max_hp=definition.max_hp)
    engine.native_streams={key:service.stream(key) for key in COMBAT_STREAMS}
    relic=STARTER_UPGRADES[definition.relic] if refined else definition.relic
    potions=[] if refined else [PotionInstance(n,f'potion.{i}') for i,n in enumerate(definition.potion_pool)]
    engine.reset(character=name,relics=[RelicInstance(relic,'relic.0')],potions=potions,potion_slots=3-len(potions))
    # Empty authored piles, separate native hand-draw modifier probe.
    for pile in (engine.player.hand,engine.player.deck.draw_pile,engine.player.deck.discard_pile):pile.clear()
    engine.enemies[0].hp=engine.enemies[0].max_hp=1000
    draw=7 if name=='silent' else 5
    assert state(engine,draw)==row['before']
    for step in row['steps']:
        other=CombatEngine(cards=DEFAULT_CARDS);other.restore(saved(engine))
        assert saved(other)==saved(engine)
        apply(engine,step,name);apply(other,step,name)
        assert saved(other)==saved(engine)
        assert state(engine,draw)==step['state']
