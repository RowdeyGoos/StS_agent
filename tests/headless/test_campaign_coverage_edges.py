"""Regressions isolated from the longer native campaign replays."""
import json
from copy import deepcopy

import pytest

from game.headless.core.actions import EndTurn
from game.headless.core.enemy_turn import turn_order
from game.headless.core.native_rng import NativeRng
from game.headless.encounters.randomness import summon
from game.headless.map.graph import MapGraph, MapNode
from game.headless.monsters.glory_summons import Axebot
from game.headless.run.actions import ChooseNode
from game.headless.run.ancient import PROFILE
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from tests.headless.test_underdocks import start, step


def test_native_neow_owns_one_event_position_before_first_unknown():
    run = RunEngine.ironclad_run(seed=4, first_act='underdocks', ancient_profile=PROFILE)
    assert run.state.event_progression.queue[:2] == ['sunken_treasury', 'trash_heap']
    assert run.state.event_progression.cursor == 1
    clone = RunEngine()
    clone.restore(json.loads(json.dumps(run.snapshot())))
    assert clone.snapshot() == run.snapshot()
    bad = deepcopy(run.snapshot())
    bad['state']['event_progression']['cursor'] = 0
    with pytest.raises(ValueError):
        clone.restore(bad)
    assert clone.snapshot() == run.snapshot()


def test_authored_row_zero_event_does_not_require_native_queue():
    graph = MapGraph((MapNode('e', 'event', (), event_id='jungle_maze_adventure', row=0, column=0),), 'e')
    run = RunEngine(config=RunConfig(), graph=graph)
    run.apply(ChooseNode('e'))
    assert run.state.pending['definition_id'] == 'jungle_maze_adventure'
    assert run.state.event_progression is None


def test_gas_bomb_native_order_preserves_stable_target_slots():
    run = start('living_fog')
    step(run, EndTurn())
    step(run, EndTurn())
    assert [e.name for e in run.combat.enemies] == ['Living Fog', 'Gas Bomb']
    assert turn_order(run.combat.enemies) == [1, 0]
    bomb = run.combat.enemies[1]
    assert bomb.position == 0
    bomb.position = 5
    with pytest.raises(ValueError):
        RunEngine().restore(run.snapshot())


def test_axebot_hp_excludes_only_present_dying_parent_not_older_dead_slots():
    run = start('living_fog')
    p = run.combat.player
    older, parent = Axebot(NativeRng(0)), Axebot(NativeRng(1))
    older.hp = parent.hp = 0
    older.max_hp, parent.max_hp = 70, 71
    p.combat_enemies[:] = [older, parent]
    parent.combat_player = p
    class ChoiceRecorder(NativeRng):
        def choice(self, values):
            assert list(values) == [70, 72, 73, 74, 75, 76, 77, 78]
            return values[0]
    p.deck.niche_rng = ChoiceRecorder(0)
    child = summon(Axebot, parent, p, stock=0, replacement=True)
    assert child.max_hp == 70


def test_stone_cracker_upgrades_in_ordinary_combat_without_changing_run_deck():
    run = RunEngine(seed=8, max_hp=1000, rng_profile='native', card_ids=['strike', 'bash', 'defend', 'pommel_strike'])
    add_relic(run.state, 'stone_cracker')
    run.start_combat(encounter_id='underdocks_living_fog', cards_per_turn=0)
    assert run.combat.player.rules.room_kind == 'combat'
    assert sum(c.upgrade_level for c in run.combat.player.deck.all_cards()) == 2
    assert all(c.upgrade_level == 0 for c in run.state.deck)
    clone = RunEngine()
    clone.restore(json.loads(json.dumps(run.snapshot())))
    assert clone.snapshot() == run.snapshot()


def test_claimed_aubergine_does_not_reprice_pending_gold():
    from game.headless.run.actions import ClaimRelic
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=8, config=RunConfig(reward_relics=('amethyst_aubergine',)))
    begin_combat_rewards(run.state, run.cards, encounter_id='overgrowth_bygone_effigy')
    amount = run.state.pending['gold']
    assert 35 <= amount <= 45
    step(run, ClaimRelic())
    assert run.state.pending['gold'] == amount
    before = run.snapshot()
    bad = deepcopy(before)
    bad['state']['pending']['gold'] += 15
    with pytest.raises(ValueError):
        run.restore(bad)
    assert run.snapshot() == before


@pytest.mark.parametrize('existing,claim', [(0, True), (1, True), (1, False)])
def test_extra_aubergine_preserves_generated_gold_and_existing_duplicates(existing, claim):
    from game.headless.run.actions import ChooseExtraReward
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=8, rng_profile='native', config=RunConfig(reward_relics=('vajra',)))
    add_relic(run.state, 'black_star')
    for _ in range(existing):
        add_relic(run.state, 'amethyst_aubergine')
    sources = [r.instance_id for r in run.state.relics if r.definition_id == 'amethyst_aubergine']
    begin_combat_rewards(run.state, run.cards, encounter_id='overgrowth_bygone_effigy')
    # Controlled legal offer isolates acquisition ownership from bag selection.
    reward = run.state.pending['extra_rewards'][0]
    reward['offers'] = ['amethyst_aubergine']
    gold = run.state.pending['gold']
    assert 35 + 15 * existing <= gold <= 45 + 15 * existing
    step(run, ChooseExtraReward(0, 'amethyst_aubergine' if claim else None))
    reward = run.state.pending['extra_rewards'][0]
    assert reward['resolved']
    assert run.state.pending['gold_bonus_sources'] == sources
    assert sum(r.definition_id == 'amethyst_aubergine' for r in run.state.relics) == existing + claim
    assert run.state.pending['gold'] == gold
    before = run.snapshot()
    for receipt in (['run.item.999999'], [1], sources * 2 if sources else [None],
                    [run.state.relics[0].instance_id]):
        bad = deepcopy(before)
        bad['state']['pending']['gold_bonus_sources'] = receipt
        with pytest.raises(ValueError):
            run.restore(bad)
        assert run.snapshot() == before


@pytest.mark.parametrize('existing', [0, 1])
def test_paels_wing_aubergine_preserves_original_gold(existing, monkeypatch):
    from game.headless.relics.run_rules import counter
    from game.headless.run.actions import SacrificeCardReward
    from game.headless.run.rewards import begin_combat_rewards
    from game.headless.generation import relics
    run = RunEngine(seed=8, rng_profile='native', config=RunConfig())
    wing = add_relic(run.state, 'paels_wing')
    counter(run.state, wing, 1)
    for _ in range(existing):
        add_relic(run.state, 'amethyst_aubergine')
    begin_combat_rewards(run.state, run.cards)
    gold = run.state.pending['gold']
    sources = list(run.state.pending['gold_bonus_sources'])
    monkeypatch.setattr(relics, 'pull', lambda *args, **kwargs: 'amethyst_aubergine')
    step(run, SacrificeCardReward())
    assert run.state.pending['card_resolved']
    assert run.state.pending['gold'] == gold
    assert run.state.pending['gold_bonus_sources'] == sources
    assert sum(r.definition_id == 'amethyst_aubergine' for r in run.state.relics) == existing + 1
