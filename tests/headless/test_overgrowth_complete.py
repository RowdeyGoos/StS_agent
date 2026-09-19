"""Native Overgrowth census, move rules and special encounter continuations."""

from copy import deepcopy
import json
from random import Random

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard, ChooseCombatCard
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.encounters.catalog import ENCOUNTERS, NATIVE_OVERGROWTH_ENCOUNTERS
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from game.headless.monsters.bygone_effigy import BygoneEffigy
from game.headless.monsters.ceremonial_beast import CeremonialBeast
from game.headless.monsters.fogmog import Fogmog, EyeWithTeeth
from game.headless.monsters.phrog_parasite import PhrogParasite, Wriggler
from game.headless.monsters.overgrowth_normal import Flyconid, Inklet, SlitheringStrangler, CubexConstruct
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.status import modify_attack_damage_for_statuses
from game.headless.run.actions import ChooseNode, LeaveRewards
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.state import RunPhase
from game.headless.map.graph import MapGraph, MapNode
from game.cli.headless_play import play_slice


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def step(combat, action):
    clone = CombatEngine()
    clone.restore(saved(combat))
    assert clone.legal_actions() == combat.legal_actions()
    clone.apply(action)
    result = combat.apply(action)
    assert saved(combat) == saved(clone)
    assert all(e.combat_player is clone.player for e in clone.enemies)
    return result


def fight(encounter, cards=(), hp=10000, draw=0):
    combat = CombatEngine(seed=7, encounter_factory=ENCOUNTERS[encounter],
                         deck_factory=lambda: [DEFAULT_CARDS.create(c) for c in cards],
                         player_max_hp=hp, cards_per_turn=draw)
    combat.reset()
    return combat


def test_native_census_is_complete_and_only_a0_content_is_enabled():
    assert len(NATIVE_OVERGROWTH_ENCOUNTERS) == 22
    assert set(NATIVE_OVERGROWTH_ENCOUNTERS.values()) == {k for k, v in ENCOUNTERS.items() if k.startswith('overgrowth_')}
    assert len(DEFAULT_MONSTERS) == 57  # Includes 21 new Underdocks types.
    assert sum(ENCOUNTERS[k].room_kind == 'elite' for k in NATIVE_OVERGROWTH_ENCOUNTERS.values()) == 3
    assert sum(ENCOUNTERS[k].room_kind == 'boss' for k in NATIVE_OVERGROWTH_ENCOUNTERS.values()) == 3
    with pytest.raises(ValueError): RunConfig(ascension=1)


@pytest.mark.parametrize('encounter', tuple(k for k in ENCOUNTERS if not k.startswith('battleworn_dummy_')))
def test_every_encounter_runs_twelve_turns_and_restores_every_boundary(encounter):
    combat = fight(encounter)
    before = saved(combat)
    for _ in range(4):
        combat.legal_actions()
        saved(combat)
    assert saved(combat) == before
    for _ in range(12):
        step(combat, EndTurn())
        assert not combat.done


@pytest.mark.parametrize('encounter', tuple(NATIVE_OVERGROWTH_ENCOUNTERS.values()))
def test_every_encounter_can_reach_victory_and_defeat_with_exact_reward_handoff(encounter):
    definition = ENCOUNTERS[encounter]
    graph = MapGraph((MapNode('fight', definition.room_kind, (), encounter),), 'fight')
    run = RunEngine(graph=graph, config=RunConfig())
    run.apply(ChooseNode('fight'))
    # Explicit synthetic outcome fixture: checks lifecycle, not policy strength.
    for _ in range(10):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive: enemy.take_damage(10000, is_attack=False)
    run.combat.resolve_external_effect()
    run.finish_combat()
    clone = RunEngine(); clone.restore(saved(run))
    assert run.state.phase is RunPhase.REWARD
    assert saved(clone) == saved(run)
    run.apply(LeaveRewards())
    if definition.room_kind == 'boss':
        assert run.state.phase is RunPhase.ACT_COMPLETE
        assert run.state.act_completion.boss_encounter_id == encounter
    else:
        assert run.state.phase is RunPhase.ROUTE
    defeated = fight(encounter, hp=1)
    for _ in range(20):
        if defeated.done: break
        step(defeated, EndTurn())
    assert defeated.done and defeated.winner == 'enemy'


@pytest.mark.parametrize('kind,hp_range,moves', [
    ('AssassinRubyRaider', (18,23), ['Killshot']*4),
    ('AxeRubyRaider', (20,22), ['Swing','Swing','Big Swing','Swing']),
    ('BruteRubyRaider', (30,33), ['Beat','Roar','Beat','Roar']),
    ('CrossbowRubyRaider', (18,21), ['Reload','Fire','Reload','Fire']),
    ('TrackerRubyRaider', (21,25), ['Track','Hounds','Hounds','Hounds']),
    ('CubexConstruct', (65,65), ['Charge Up','Repeater Blast','Repeater Blast','Expel Blast']),
    ('SnappingJaxfruit', (31,33), ['Energy Orb']*4),
    ('VineShambler', (61,61), ['Swipe','Grasping Vines','Chomp','Swipe']),
    ('BygoneEffigy', (127,127), ['Sleep','Wake','Slash','Slash']),
    ('KinPriest', (190,190), ['Orb of Frailty','Orb of Weakness','Beam','Ritual']),
    ('PhrogParasite', (61,64), ['Infect','Lash','Infect','Lash']),
    ('ShrinkerBeetle', (38,40), ['Shrinker','Chomp','Stomp','Chomp']),
])
def test_native_hp_ranges_and_full_move_cycles(kind,hp_range,moves):
    observed = {DEFAULT_MONSTERS[kind](Random(seed)).hp for seed in range(150)}
    assert observed == set(range(hp_range[0],hp_range[1]+1))
    enemy = DEFAULT_MONSTERS[kind](Random(2))
    actual=[]
    for _ in moves:
        actual.append(enemy.intent.move_name); enemy.advance_intent()
    assert actual == moves


def test_native_composition_variants_and_stable_slots():
    raider_sets=set(); strangler_sets=set(); flyconid_slimes=set(); small_orders=set()
    for seed in range(100):
        raiders=ENCOUNTERS['overgrowth_ruby_raiders'](Random(seed))
        assert len(raiders)==len({type(e) for e in raiders})==3
        raider_sets.update(type(e).__name__ for e in raiders)
        stranglers=ENCOUNTERS['overgrowth_strangler'](Random(seed))
        assert isinstance(stranglers[-1],SlitheringStrangler)
        strangler_sets.add(tuple(type(e).__name__ for e in stranglers[:-1]))
        flyconid_slimes.add(type(ENCOUNTERS['overgrowth_flyconid'](Random(seed))[0]).__name__)
        slimes=ENCOUNTERS['overgrowth_slimes_normal'](Random(seed))
        assert [type(e).__name__ for e in slimes[:2]]==['TwigSlimeMedium','LeafSlimeMedium']
        small_orders.add(tuple(type(e).__name__ for e in slimes[2:]))
    assert len(raider_sets)==5 and len(strangler_sets)==7 and len(flyconid_slimes)==2 and len(small_orders)==2
    inklets=ENCOUNTERS['overgrowth_inklets'](Random(0))
    assert [e.intent.move_name for e in inklets]==['Jab','Whirlwind','Jab']
    kin=ENCOUNTERS['overgrowth_the_kin'](Random(0))
    assert [e.intent.move_name for e in kin]==['Dance','Quick Slash','Orb of Frailty']


def test_flyconid_native_cooldowns_and_exhausted_weight_fallback():
    enemy=Flyconid(Random(4))
    assert enemy.intent.move_name in ('Frail Spores','Smash')
    enemy._intent_index=0;enemy.vulnerable_cooldown=enemy.frail_cooldown=0
    enemy.advance_intent()
    assert enemy._intent_index in (1,2) and enemy.vulnerable_cooldown==3
    # The native selector picks its first branch with NextFloat(0) when every
    # move is excluded: source-observed fallback, not a fabricated extra move.
    enemy._intent_index=2;enemy.vulnerable_cooldown=2;enemy.frail_cooldown=2
    before=enemy.rng.getstate();enemy.advance_intent()
    assert enemy._intent_index==0 and enemy.rng.getstate()!=before


def test_artifact_consumes_one_debuff_application_and_frail_is_card_block_only():
    combat=fight('overgrowth_cubex',cards=('shockwave','defend'),draw=2)
    enemy=combat.enemies[0]
    assert enemy.block==13 and enemy.statuses.get('artifact')==1
    enemy.apply_status('weak',2);enemy.apply_status('vulnerable',2)
    assert enemy.statuses.get('artifact')==enemy.statuses.get('weak')==0
    assert enemy.statuses.get('vulnerable')==2
    player=combat.player;player.apply_status('frail',2)
    defend=next(c for c in player.hand if c.definition.definition_id=='defend')
    step(combat,PlayCard(defend.instance_id))
    assert player.block==3
    player.gain_block(12)
    assert player.block==15
    step(combat,EndTurn());assert player.statuses.get('frail')==2
    step(combat,EndTurn());assert player.statuses.get('frail')==1
    step(combat,EndTurn());assert player.statuses.get('frail')==0


def test_tangled_attack_cost_and_ringing_legality_survive_restore():
    combat=fight('overgrowth_vine_shambler',cards=('strike','strike','defend'),draw=3)
    player=combat.player;player.apply_status('tangled',1);player.apply_status('ringing',1)
    strike=next(c for c in player.hand if c.definition.definition_id=='strike')
    assert player.card_cost(strike)==2
    step(combat,PlayCard(strike.instance_id,0))
    assert player.energy==1 and combat.legal_actions()==(EndTurn(),)
    step(combat,EndTurn())
    assert player.cards_played_this_turn==0
    assert player.statuses.get('ringing')==player.statuses.get('tangled')==0


def test_constrict_damage_uses_block_and_clears_when_its_applier_dies():
    combat=fight('overgrowth_strangler');source=combat.enemies[-1]
    step(combat,EndTurn());assert combat.player.statuses.get('constrict')==3
    combat.player.block=2;hp=combat.player.hp
    # End-player-side damage happens before the next enemy attacks.
    combat.player.end_turn()
    from game.headless.powers.lifecycle import after_owner_side_turn_end
    after_owner_side_turn_end(combat.player)
    assert combat.player.hp==hp-1 and combat.player.block==0
    source.take_damage(999,is_attack=False)
    assert combat.player.statuses.get('constrict')==0 and 'constrict' not in combat.player.power_sources


def test_shrink_combines_fractions_and_clears_at_source_death_between_effects():
    assert modify_attack_damage_for_statuses(7,{'vulnerable':1},attacker_statuses={'shrink':1})==7
    combat=fight('overgrowth_crawlers');beetle=combat.enemies[0]
    step(combat,EndTurn());assert combat.player.statuses.get('shrink')==1
    beetle.take_damage(999,is_attack=False)
    assert combat.enemies[1].is_alive and combat.player.statuses.get('shrink')==0


def test_slow_counts_completed_cards_once_and_multihits_share_multiplier():
    combat=fight('overgrowth_bygone_effigy',cards=('defend','sword_boomerang','armaments','strike'),draw=4)
    enemy=combat.enemies[0];player=combat.player;player.energy=10
    defend=next(c for c in player.hand if c.definition.definition_id=='defend')
    step(combat,PlayCard(defend.instance_id));assert enemy.slow_count==1
    boomerang=next(c for c in player.hand if c.definition.definition_id=='sword_boomerang')
    hp=enemy.hp;step(combat,PlayCard(boomerang.instance_id))
    assert hp-enemy.hp==9 and enemy.slow_count==2
    armaments=next(c for c in player.hand if c.definition.definition_id=='armaments')
    step(combat,PlayCard(armaments.instance_id))
    assert enemy.slow_count==3  # sole remaining Strike auto-selects
    step(combat,EndTurn());assert enemy.slow_count==0
    assert enemy.intent.move_name=='Wake'


def test_plow_threshold_stun_strength_reset_and_second_phase_cycle():
    combat=fight('overgrowth_ceremonial_beast');enemy=combat.enemies[0]
    step(combat,EndTurn());assert enemy.statuses.get('plow')==150
    step(combat,EndTurn());assert enemy.strength==2
    enemy.take_damage(101,is_attack=False)
    assert enemy.hp==151 and enemy.intent.move_name=='Plow'
    enemy.block=100;enemy.take_damage(100,is_attack=False)
    assert enemy.hp==151 and enemy.intent.move_name=='Plow'
    enemy.take_damage(1,is_attack=False)
    assert enemy.hp==150 and enemy.intent.move_name=='Stunned' and enemy.strength==0
    assert enemy.statuses.get('plow')==0
    for expected in ('Beast Cry','Stomp','Crush','Beast Cry'):
        step(combat,EndTurn());assert enemy.intent.move_name==expected
    assert enemy.strength==3


def test_phrog_death_summons_four_primary_enemies_before_multihit_continues():
    combat=fight('overgrowth_phrog_parasite',cards=('sword_boomerang',),draw=1)
    phrog=combat.enemies[0];phrog.hp=1
    step(combat,PlayCard(combat.player.hand[0].instance_id))
    assert not combat.done and phrog.hp==0 and len(combat.enemies)==5
    children=combat.enemies[1:]
    assert all(isinstance(e,Wriggler) and not e.statuses.get('minion') for e in children)
    assert sum(e.max_hp-e.hp for e in children)==6
    assert all(e.intent.move_name=='Spawned' for e in children)
    step(combat,EndTurn())
    assert [e.intent.move_name for e in children]==['Bite','Wriggle','Bite','Wriggle']
    step(combat,EndTurn())
    assert [e.strength for e in children]==[0,2,0,2]
    assert sum(c.definition.definition_id=='infection' for pile in ('draw_pile','discard_pile','hand') for c in getattr(combat.player.deck,pile))==2
    assert len(combat.enemies)==5


def test_illusion_revives_in_place_without_an_attack_and_dies_with_fogmog():
    combat=fight('overgrowth_fogmog')
    step(combat,EndTurn());assert len(combat.enemies)==2
    eye=combat.enemies[1]
    assert eye.hp==6 and not combat.player.deck.discard_pile  # no immediate summon turn
    for _ in range(2):
        eye.take_damage(999,is_attack=False)
        assert not eye.is_alive and eye.intent.move_name=='Revive'
        before=len(combat.player.deck.discard_pile)
        step(combat,EndTurn())
        assert eye.is_alive and eye.hp==6 and len(combat.player.deck.discard_pile)==before
        step(combat,EndTurn())
        assert len(combat.player.deck.discard_pile)==before+3
    combat.enemies[0].take_damage(999,is_attack=False)
    combat.resolve_external_effect()
    assert combat.winner=='player' and eye.hp==0


def test_priest_death_ends_combat_without_retargeting_secondary_followers():
    combat=fight('overgrowth_the_kin',cards=('fiend_fire','defend','defend'),draw=3)
    priest=combat.enemies[2];priest.hp=1
    card=next(c for c in combat.player.hand if c.definition.definition_id=='fiend_fire')
    step(combat,PlayCard(card.instance_id,2))
    assert combat.winner=='player' and all(e.hp==0 for e in combat.enemies)


def test_infection_and_dazed_end_hand_rules_and_no_permanent_deck_leak():
    combat=fight('overgrowth_cubex',cards=('infection','infection','dazed'),draw=3)
    combat.player.block=4;hp=combat.player.hp
    step(combat,EndTurn())
    assert combat.player.hp==hp-2  # two separate 3-damage packets consume block
    assert [c.definition.definition_id for c in combat.player.deck.exhaust_pile]==['dazed']
    dying=fight('overgrowth_cubex',cards=('infection',),draw=1,hp=2)
    result=step(dying,EndTurn())
    assert dying.winner=='enemy' and result.details['enemy_actions']==[]


@pytest.mark.parametrize('mutation', ['counter','source','source_dead','phase','cooldown','schema'])
def test_new_private_state_rejects_malformed_restore_atomically(mutation):
    combat=fight('overgrowth_crawlers' if mutation.startswith('source') else 'overgrowth_flyconid')
    if mutation.startswith('source'):step(combat,EndTurn())
    before=saved(combat);bad=deepcopy(before)
    if mutation=='counter':bad['player']['cards_played_this_turn']=True
    elif mutation=='source':bad['player']['power_sources']['shrink']=99
    elif mutation=='source_dead':bad['enemies'][0]['state']['hp']=0
    elif mutation=='phase':bad['enemies'][0]['state']['_intent_index']=9
    elif mutation=='cooldown':bad['enemies'][0]['state']['frail_cooldown']=-1
    elif mutation=='schema':bad['schema']='headless_combat_state_v4'
    with pytest.raises(ValueError):combat.restore(bad)
    assert saved(combat)==before


@pytest.mark.parametrize('boss', ['overgrowth_vantom','overgrowth_ceremonial_beast','overgrowth_the_kin'])
def test_authored_route_can_select_every_boss_and_restore(boss):
    run=RunEngine.ironclad_slice(route='overgrowth-act1',boss=boss,elite='overgrowth_bygone_effigy',hallway='overgrowth_cubex')
    assert run.graph.node('vantom').encounter_id==boss
    assert run.graph.node('byrdonis').encounter_id=='overgrowth_bygone_effigy'
    assert run.graph.node('mawler').encounter_id=='overgrowth_cubex'
    clone=RunEngine();clone.restore(saved(run));assert saved(clone)==saved(run)
    with pytest.raises(ValueError):RunEngine.ironclad_slice(boss=boss)
    with pytest.raises(ValueError):RunEngine.ironclad_slice(route='overgrowth-act1',boss='overgrowth_shrinker')


@pytest.mark.parametrize('encounter,packets,strengths', [
    ('overgrowth_cubex', [0,9,11,22], [2,4,6,6]),
    ('overgrowth_bygone_effigy', [0,0,23,23], [0,10,10,10]),
    ('overgrowth_phrog_parasite', [0,16,0,16], [0,0,0,0]),
    ('overgrowth_vine_shambler', [12,8,16,12], [0,0,0,0]),
])
def test_native_four_turn_damage_and_self_strength(encounter,packets,strengths):
    combat=fight(encounter)
    for damage,strength in zip(packets,strengths):
        hp=combat.player.hp;step(combat,EndTurn())
        assert hp-combat.player.hp==damage
        assert combat.enemies[0].strength==strength


def test_eye_death_clears_debuffs_before_reviving():
    combat=fight('overgrowth_fogmog');step(combat,EndTurn())
    eye=combat.enemies[1]
    for name in ('weak','vulnerable','frail'):eye.apply_status(name,3)
    eye.take_damage(999,is_attack=False)
    assert all(eye.statuses.get(name)==0 for name in ('weak','vulnerable','frail'))
    assert eye.statuses.get('illusion')==eye.statuses.get('minion')==1
    step(combat,EndTurn());assert eye.hp==6


@pytest.mark.parametrize('live', [True,False])
def test_corrupt_phrog_spawn_relationship_cannot_skip_or_duplicate_children(live):
    combat=fight('overgrowth_phrog_parasite')
    if not live:combat.enemies[0].take_damage(999,is_attack=False)
    before=saved(combat);bad=deepcopy(before)
    bad['enemies'][0]['state']['spawned']=live
    with pytest.raises(ValueError):combat.restore(bad)
    assert saved(combat)==before
    if not live:
        bad=deepcopy(before);bad['enemies']=bad['enemies'][:1]
        bad['done']=True;bad['winner']='player'
        with pytest.raises(ValueError):combat.restore(bad)
        assert saved(combat)==before


def test_last_primary_death_stops_draw_suffix_immediately():
    combat=fight('overgrowth_fogmog',cards=('pommel_strike','strike'),draw=1)
    step(combat,EndTurn())
    player=combat.player
    cards=player.deck.draw_pile+player.hand+player.deck.discard_pile
    player.deck.hand=[next(c for c in cards if c.definition.definition_id=='pommel_strike')]
    player.deck.draw_pile=[next(c for c in cards if c.definition.definition_id=='strike')]
    player.deck.discard_pile=[]
    combat.enemies[0].hp=1
    step(combat,PlayCard(player.hand[0].instance_id,0))
    assert combat.winner=='player' and len(player.deck.draw_pile)==1 and not player.hand


def test_oracle_clone_owns_context_and_power_sources_independently():
    from game.simulation.core import CombatEnv
    from game.analysis.bruteforce import clone_combat_env, _combat_state_key, _RngStateRegistry, _CardStateRegistry
    env=CombatEnv();env.reset()
    clone=clone_combat_env(env)
    assert clone.player.power_sources is not env.player.power_sources
    assert all(e.combat_player is clone.player for e in clone.enemies)
    rngs,cards=_RngStateRegistry(),_CardStateRegistry()
    before=_combat_state_key(env,rngs,cards)
    env.player.cards_played_this_turn+=1
    assert _combat_state_key(env,rngs,cards)!=before


@pytest.mark.parametrize('hp,phase', [(0,0),(6,1)])
def test_illusion_snapshot_requires_death_and_revive_to_match(hp,phase):
    combat=fight('overgrowth_fogmog');step(combat,EndTurn())
    before=saved(combat);bad=deepcopy(before)
    bad['enemies'][1]['state'].update(hp=hp,_intent_index=phase)
    with pytest.raises(ValueError):combat.restore(bad)
    assert saved(combat)==before


def test_snapshot_rejects_a_live_but_wrong_power_applier_and_wrong_beast_phase():
    combat=fight('overgrowth_crawlers');step(combat,EndTurn())
    before=saved(combat);bad=deepcopy(before)
    bad['player']['power_sources']['shrink']=1
    with pytest.raises(ValueError):combat.restore(bad)
    assert saved(combat)==before
    beast=fight('overgrowth_ceremonial_beast');step(beast,EndTurn())
    before=saved(beast);bad=deepcopy(before)
    bad['enemies'][0]['state']['_intent_index']=4
    with pytest.raises(ValueError):beast.restore(bad)
    assert saved(beast)==before
