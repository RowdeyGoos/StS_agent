"""Event-owned composition; these never enter ordinary encounter queues."""
from functools import partial
from game.headless.encounters.base import EncounterDefinition
from game.headless.encounters.randomness import create
from game.headless.monsters.event_monsters import BattleFriendV1,BattleFriendV2,BattleFriendV3,PunchConstruct,MysteriousKnight,FakeMerchantMonster


def solo(kind,rng): return [create(kind,rng)]


def punch_off(rng):
    left=rng.randrange(2,10);right=rng.randrange(2,10)
    return [create(PunchConstruct,rng,fast=True,reduction=left),create(PunchConstruct,rng,reduction=right)]


ENCOUNTERS={
    **{f'battleworn_dummy_{i}':EncounterDefinition(partial(solo,cls),gold_range=(0,0),event_id='battleworn_dummy') for i,cls in enumerate((BattleFriendV1,BattleFriendV2,BattleFriendV3),1)},
    'punch_off_event':EncounterDefinition(punch_off,event_id='punch_off'),
    'mysterious_knight_event':EncounterDefinition(partial(solo,MysteriousKnight),event_id='the_lantern_key'),
    'fake_merchant_event':EncounterDefinition(partial(solo,FakeMerchantMonster),gold_range=(300,300),event_id='fake_merchant'),
}
NATIVE_IDS={**{f'battleworn_dummy_{i}':'BattlewornDummyEventEncounter' for i in range(1,4)},'punch_off_event':'PunchOffEventEncounter','mysterious_knight_event':'MysteriousKnightEventEncounter','fake_merchant_event':'FakeMerchantEventEncounter'}
