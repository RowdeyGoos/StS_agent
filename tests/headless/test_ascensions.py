"""Pinned A0–A10 native scalar/map vectors and source-backed run continuations."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
from types import SimpleNamespace

import pytest

from game.headless.core.actions import EndTurn
from game.headless.core.ascension import ancient_heal, gold_range
from game.headless.core.combat import CombatEngine
from game.headless.core.native_rng import single
from game.headless.core.native_service import NativeRandomService
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.generation import odds
from game.headless.generation.initialization import generate
from game.headless.generation.relics import populate
from game.headless.map.standard import generate_map, SPOILS_PROFILE
from game.headless.monsters.ascension_values import VALUES, HP
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from game.headless.run.actions import ContinueAct, LeaveRewards
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.shop import removal_price, eligible_removals
from game.headless.run.state import RunPhase

FIXTURES = Path(__file__).parents[1] / 'fixtures'
NATIVE = json.loads((FIXTURES / 'headless_native_ascension_vectors.json').read_text())
MAPS = json.loads((FIXTURES / 'headless_native_ascension_maps.json').read_text())
ALIASES = {'LeafSlimeSmall': 'LeafSlimeS', 'LeafSlimeMedium': 'LeafSlimeM',
           'TwigSlimeSmall': 'TwigSlimeS', 'TwigSlimeMedium': 'TwigSlimeM',
           **{f'DecimillipedeSegment{part}': 'DecimillipedeSegment' for part in ('Front', 'Middle', 'Back')}}


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    copy = RunEngine()
    copy.restore(saved(run))
    assert saved(copy) == saved(run)
    assert copy.legal_actions() == run.legal_actions()
    return copy


@pytest.mark.parametrize('level', range(11))
def test_cumulative_startup_and_owned_level_roundtrip(level):
    run = RunEngine.ironclad_run(seed=4, ascension=level)
    assert run.state.hp == (64 if level >= 2 else 80)
    assert run.state.potion_capacity == (2 if level >= 4 else 3)
    assert len(run.state.potions) == run.state.potion_capacity
    bane = [c for c in run.state.deck if c.definition.definition_id == 'ascenders_bane']
    assert len(bane) == int(level >= 5)
    if bane:
        assert bane[0].spec.eternal and bane[0].spec.ethereal
        assert bane[0].instance_id not in eligible_removals(run.state)
    clone(run)
    run.apply(run.legal_actions()[0])
    assert run.combat.ascension == level
    assert all(e.ascension == level for e in run.combat.enemies)
    clone(run)


@pytest.mark.parametrize('level', [-1, 11, True, 1.0, '8', None])
def test_invalid_ascension_rejects(level):
    with pytest.raises(ValueError): RunConfig(ascension=level)
    with pytest.raises(ValueError): CombatEngine(ascension=level)


@pytest.mark.parametrize('row', NATIVE['rows'], ids=lambda r: f"A{r['ascension']}")
def test_monster_scalars_hp_and_economy_match_native_getters(row):
    assert NATIVE['contextCleared']
    level = row['ascension']
    native = {m['type']: m['values'] for m in row['monsters']}
    for name, properties in VALUES.items():
        expected = native[ALIASES.get(name, name)]
        for prop, (threshold, low, high) in properties.items():
            if prop == 'PlatingAmount' and name == 'SewerClam':
                continue  # Source constant in AddInitialPowers, no native getter.
            assert (high if level >= threshold else low) == expected[prop], (name, prop, level)
        if level >= 8 and name in HP:
            assert HP[name] == (expected['MinInitialHp'], expected['MaxInitialHp']), name
    run = RunEngine(config=RunConfig(ascension=level))
    for count in (0, 1, 3):
        run.state.shop_removals_used = count
        assert removal_price(run.state) == row['removalBase'] + count * row['removalIncrement']
    for encounter, bounds in zip(row['encounters'][:3], ((10, 20), (35, 45), (100, 100))):
        assert gold_range(run.state, bounds) == (encounter['min'], encounter['max'])
    fake = next(e for e in ENCOUNTERS.values() if e.event_id == 'fake_merchant')
    assert not fake.ascension_gold and fake.gold_range == (300, 300)
    assert row['encounters'][3]['min'] == row['encounters'][3]['max'] == 300
    assert row['elites'] == (8 if level else 5)
    run.state.rng = SimpleNamespace(random=lambda _: 0.99)
    run.state.generation_odds = odds.initial()
    assert odds.rarity(run.state) == 'common'
    assert run.state.generation_odds['card_offset'] == single(single(-.05) + single(row['rarityGrowth']))
    for kind, key in (('combat', 'rareCombat'), ('elite', 'rareElite'), ('shop', 'rareShop')):
        run.state.rng = SimpleNamespace(random=lambda _, p=row[key]: single(p) - 1e-7)
        assert odds.rarity(run.state, kind, mode='base') == 'rare'
        run.state.rng = SimpleNamespace(random=lambda _, p=row[key]: single(p))
        assert odds.rarity(run.state, kind, mode='base') == 'uncommon'


@pytest.mark.parametrize('row', MAPS['rows'], ids=lambda r: f"A{r['ascension']}-{r['mode']}-{r['seed']}")
def test_native_higher_ascension_map_queues_and_rng_suffixes(row):
    level = row['ascension']
    rng = NativeRandomService(row['seed'])
    populate(rng)
    assert rng.request_count('up_front') == row['afterBags']
    first = row['acts'][0]['act']
    actual = generate(rng, act=first, ascension=level)
    assert actual['subsets'] == row['subsets']
    assert actual['acts'] == row['acts']
    assert rng.request_count('up_front') == row['upFrontCounter']
    assert rng.double('up_front') == row['upFrontSuffix']
    act = 'hive' if row['mode'] == 'spoils' else row['mode']
    graph = generate_map(rng, event_pool=('relic_trader',), act=act, ascension=level,
                         profile=SPOILS_PROFILE if row['mode'] == 'spoils' else None,
                         second_boss=level == 10 and act == 'glory')
    kinds = dict(Monster='combat', Elite='elite', Unknown='unknown', RestSite='rest', Treasure='treasure', Shop='shop', Boss='boss')
    assert [dict(coord=[n.row, n.column], kind=n.kind,
                 children=sorted([[graph.node(i).row, graph.node(i).column] for i in n.next_node_ids]))
            for n in graph.nodes] == [dict(n, kind=kinds[n['kind']]) for n in row['map']['nodes']]
    assert [[graph.node(i).row, graph.node(i).column] for i in graph.entry_node_ids] == row['map']['starts']
    stream = 'spoils_map' if row['mode'] == 'spoils' else f"act{1 if act in ('overgrowth', 'underdocks') else 2 if act == 'hive' else 3}.map"
    assert rng.request_count(stream) == row['map']['counter']
    assert rng.double(stream) == row['map']['suffix']


@pytest.mark.parametrize('level', [1, 2, 10])
def test_ancient_heals_missing_hp_with_native_truncation(level):
    run = RunEngine(config=RunConfig(ascension=level), max_hp=81, hp=12)
    ancient_heal(run.state)
    assert run.state.hp == (67 if level >= 2 else 81)
    ancient_heal(run.state, neow=True)
    assert run.state.hp == (64 if level >= 2 else 81)


@pytest.mark.parametrize('level', [6, 7])
def test_scarcity_upgrade_draw_and_rare_zero_chance(level):
    from game.headless.cards.catalog import DEFAULT_CARDS
    run = RunEngine(config=RunConfig(ascension=level), rng_profile='native')
    run.state.act_index = 1
    calls = []
    def roll(stream):
        calls.append(stream)
        return .2
    run.state.rng = SimpleNamespace(random=roll, choice=lambda _, pool: pool[0])
    names, upgraded = odds.card_offers(run.state, DEFAULT_CARDS, ('shrug_it_off',), uniform=True)
    assert names == ['shrug_it_off'] and upgraded == ([] if level == 7 else names)
    assert calls == ['rewards']
    assert odds.card_offers(run.state, DEFAULT_CARDS, ('demon_form',), uniform=True)[1] == []


@pytest.mark.parametrize('level', [8, 9])
@pytest.mark.parametrize('encounter', ENCOUNTERS)
def test_every_encounter_higher_ascension_turns_and_serializable_continuation(level, encounter):
    run = RunEngine(seed=4, max_hp=100000, config=RunConfig(ascension=level), card_ids=(), rng_profile='native')
    if ENCOUNTERS[encounter].event_id:
        combat = CombatEngine(seed=4, ascension=level, player_max_hp=100000,
                              deck_factory=lambda: (), encounter_factory=ENCOUNTERS[encounter])
        combat.reset()
        for _ in range(6):
            if combat.done: break
            actions = combat.legal_actions()
            combat.apply(EndTurn() if EndTurn() in actions else actions[0])
        other = CombatEngine()
        other.restore(json.loads(json.dumps(combat.snapshot())))
        assert other.snapshot() == combat.snapshot()
        assert all(e.ascension == level for e in combat.enemies)
        return
    run.start_combat(encounter_id=encounter, cards_per_turn=0)
    for _ in range(6):
        if run.combat is None or run.combat.done:
            break
        actions = run.legal_actions()
        run.apply(EndTurn() if EndTurn() in actions else actions[0])
    if run.combat is None:
        clone(run)
        return
    assert all(e.ascension == level for e in run.combat.enemies)
    other = clone(run)
    if not run.combat.done:
        actions = run.legal_actions()
        action = EndTurn() if EndTurn() in actions else actions[0]
        run.apply(action); other.apply(action)
        assert saved(run) == saved(other)


def test_ascension_is_instance_owned_and_representative_intents_are_exact():
    from game.headless.monsters.glory_elites import MagiKnight
    from game.headless.monsters.overgrowth_normal import Flyconid
    from game.headless.monsters.byrdonis import Byrdonis
    for level in (9, 0, 8, 0):
        rng = MonsterConstruction(Random(2), None, ascension=level)
        magi = MagiKnight(rng)
        magi._intent_index = 3
        assert magi.intent.block_gain == (9 if level >= 8 else 5)
        fly = Flyconid(rng); fly._intent_index = 0
        assert fly.intent.attack_count == fly.intent.attack_damage == 0
        byrd = Byrdonis(rng); byrd._intent_index = 0
        assert byrd.intent.attack_count == 3
        assert byrd.intent.attack_damage == (4 if level >= 9 else 3)


@pytest.mark.parametrize('profile', ['native', 'fixture'])
def test_a10_final_bosses_are_distinct_and_both_required_without_ancient_heal(profile):
    from tests.headless.test_act2_run import complete_act, win
    from game.cli.headless_play import choose_demo_action
    run = RunEngine.ironclad_run(seed=4, ascension=10, rng_profile=profile)
    run.state.max_hp = run.state.hp = 100000
    for _ in range(2):
        complete_act(run)
        run.apply(ContinueAct())
    progression = run.state.encounter_progression
    assert progression.boss != progression.second_boss
    for _ in range(400):
        if run.combat:
            win(run)
        if run.state.phase is RunPhase.REWARD and run.graph.node(run.state.current_node_id).kind == 'boss':
            break
        run.apply(choose_demo_action(run, rest_choice='rest'))
    else: pytest.fail('Did not reach first Glory boss')
    assert run.state.pending['encounter_id'] == progression.boss
    assert LeaveRewards() in run.legal_actions()
    assert run.state.pending['offers'] == [] and run.state.pending['gold'] == 0
    run.state.hp = 1234
    run.apply(LeaveRewards())
    assert run.state.phase is RunPhase.ROUTE and run.state.hp == 1234
    clone(run)
    run.apply(run.legal_actions()[0])
    assert run.state.active_encounter_id == progression.second_boss
    # Combat-start relic/card healing still applies normally in the next fight.
    win(run)
    run.apply(LeaveRewards())
    assert run.state.phase is RunPhase.ACT_COMPLETE
    clone(run)


@pytest.mark.parametrize('corrupt', [
    lambda s: s['state']['config'].__setitem__('ascension', 11),
    lambda s: s['combat']['config'].__setitem__('ascension', 8),
    lambda s: s['combat']['enemies'][0]['state'].__setitem__('ascension', 8),
    lambda s: s.__setitem__('schema', 'headless_run_state_v59'),
])
def test_ascension_snapshot_mismatch_rejects_atomically(corrupt):
    run = RunEngine(config=RunConfig(ascension=9))
    run.start_combat(encounter_id='overgrowth_nibbits')
    before = saved(run)
    bad = deepcopy(before)
    corrupt(bad)
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('level', [0, 8, 9])
def test_axebot_replacements_scale_strength_per_remaining_life(level):
    from game.headless.monsters.glory_summons import Axebot
    for stock in (2, 1, 0):
        combat = CombatEngine(seed=4, ascension=level, player_max_hp=10000,
                             encounter_factory=lambda rng: [Axebot(rng, stock=stock, replacement=True)])
        combat.reset()
        enemy = combat.enemies[0]
        combat.apply(EndTurn())
        assert enemy.strength == (4 if level >= 9 else 3) * (2 - stock)
        assert enemy.block == (15 if level >= 9 else 10)


@pytest.mark.parametrize('level', [7, 8, 9])
def test_test_subject_revives_at_each_native_hp_and_growl_scales(level):
    from game.headless.monsters.glory_bosses import TestSubject as Subject
    combat = CombatEngine(seed=4, ascension=level, player_max_hp=10000,
                         encounter_factory=lambda rng: [Subject(rng)])
    combat.reset()
    enemy = combat.enemies[0]
    assert enemy.max_hp == (111 if level >= 8 else 100)
    for hp in ((212, 313) if level >= 8 else (200, 300)):
        enemy.take_damage(10000, is_attack=False)
        combat.resolve_external_effect()
        assert enemy.reviving
        combat.apply(EndTurn())
        assert enemy.max_hp == enemy.hp == hp
        other = CombatEngine(); other.restore(json.loads(json.dumps(combat.snapshot())))
        assert other.snapshot() == combat.snapshot()
    enemy._intent_index = 6
    assert len(enemy.intent.discard_cards) == (5 if level >= 9 else 3)
    assert enemy.intent.strength_gain == (3 if level >= 9 else 2)


def test_a10_golden_compass_native_single_boss_exception_reaches_epilogue():
    from tests.headless.test_act2_run import complete_act
    from game.headless.run.actions import ChooseEventOption
    run = RunEngine.ironclad_run(seed=4, ascension=10)
    run.state.max_hp = run.state.hp = 100000
    for _ in range(2):
        complete_act(run); run.apply(ContinueAct())
    run.obtain_relic('golden_compass')
    assert run.state.encounter_progression.second_boss is not None
    assert sum(n.kind == 'boss' for n in run.graph.nodes) == 1
    clone(run)
    complete_act(run)
    clone(run)
    run.apply(ContinueAct())
    run.apply(ChooseEventOption(run.state.epilogue_event_id, 'proceed'))
    assert run.state.phase is RunPhase.VICTORY
    clone(run)


@pytest.mark.parametrize('seed', range(5))
def test_poverty_chest_scales_after_the_same_random_draw(seed):
    from game.headless.run import treasure
    amounts, streams = [], []
    for level in (2, 3):
        run = RunEngine(seed=seed, config=RunConfig(ascension=level), rng_profile='native')
        treasure.begin(run.state)
        amounts.append(treasure.open_chest(run.state))
        streams.append(run.state.rng.snapshot())
        clone(run)
    assert amounts[1] == amounts[0] * 3 // 4
    assert streams[0] == streams[1]
