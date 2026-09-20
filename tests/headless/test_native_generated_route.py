"""Continuous native Act 1 trace; every Python action also resumes from JSON."""
import hashlib
import json
import re
from pathlib import Path

from game.headless.core.actions import EndTurn, PlayCard
from game.headless.run import ancient
from game.headless.run.actions import (
    ChooseAncientRelic, ChooseNode, ChooseRelicReward, ChooseRewardCard,
    ClaimGold, ClaimRelic, LeaveRest, LeaveRewards, LeaveShop, LeaveTreasure, Rest,
)
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from tests.headless.test_act2_run import step
from tests.headless.test_native_generated_start import card_id

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_generated_route_2026_09_20.json').read_text())
LEGACY = json.loads((ROOT / 'docs/evidence/native_generated_start_route_regression_2026_09_20.json').read_text())


def combat_boundary(run):
    player = run.combat.player
    return dict(
        hp=player.hp, block=player.block, energy=player.energy,
        hand=[dict(id=card_id(c), upgrade=c.upgrade_level) for c in player.hand],
        enemies=[dict(id=re.sub('[()]', '', e.name.upper()).replace(' ', '_'),
                      hp=e.hp, block=e.block) for e in run.combat.enemies if e.is_alive],
    )


def run_boundary(run):
    state = run.state
    return dict(
        hp=state.hp, gold=state.gold,
        relics=[r.definition_id.upper() for r in state.relics],
        deck=[dict(id=card_id(c), upgrade=c.upgrade_level) for c in state.deck],
        rewardsCounter=state.rng.request_count('rewards'),
        nicheCounter=state.rng.request_count('niche'),
        shuffleCounter=state.rng.request_count('shuffle'),
    )


def test_route_fixture_identity_and_first_combat_regression():
    for record in (RECORD, LEGACY):
        assert record['userDirectoryRemoved']
        for name, digest in record['fixtureSources'].items():
            assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest
    previous = json.loads((ROOT / 'docs/evidence/native_generated_start_verified_2026_09_20.json').read_text())
    assert LEGACY['result'] == previous['result']


def test_generated_route_matches_native_through_boss_defeat():
    row, = RECORD['result']['rows']
    run = RunEngine.ironclad_run(seed=int(row['seed']), ancient_profile=ancient.PROFILE)
    assert [a.definition_id.upper() for a in run.legal_actions()] == row['offers']
    step(run, ChooseAncientRelic(row['choice'].lower()))
    step(run, ChooseRelicReward(0))
    assert run.state.rng.request_count('rewards') == row['rewardsAfterNeow']
    assert len(row['route']) == 16
    assert sum(len(room.get('combat', {}).get('actions', [])) for room in row['route']) == 170
    for room in row['route']:
        node = next(n for n in run.graph.nodes if (n.row, n.column) == (room['row'], room['col']))
        step(run, ChooseNode(node.node_id))
        assert run_boundary(run) == room['entry'], (room['row'], 'entry')
        if room['kind'] == 'CombatRoom':
            assert combat_boundary(run) == room['combat']['initial']
            for action in room['combat']['actions']:
                if action['kind'] == 'play':
                    card = run.combat.player.hand[action['index']]
                    assert dict(id=card_id(card), upgrade=card.upgrade_level) == action['card']
                    # Native removes dead creatures; headless retains stable slots.
                    living = [e for e in run.combat.enemies if e.is_alive]
                    target = living[action['targetIndex']] if action['targetIndex'] >= 0 else None
                    slot = run.combat.enemies.index(target) if target else None
                    command = next(a for a in run.legal_actions() if isinstance(a, PlayCard)
                                   and a.instance_id == card.instance_id and a.target_slot in (None, slot))
                else:
                    assert action['kind'] == 'end'
                    command = EndTurn()
                step(run, command)
                if action['state'] is not None:
                    assert combat_boundary(run) == action['state']
            if room['rewards'] is not None:
                for reward in room['rewards']['claims']:
                    if reward['kind'] == 'GoldReward':
                        assert run.state.pending['gold'] == reward['amount']
                        step(run, ClaimGold())
                    elif reward['kind'] == 'RelicReward':
                        assert run.state.pending['relic'].upper() == reward['relic']
                        step(run, ClaimRelic())
                    else:
                        assert reward['kind'] == 'CardReward'
                        pending = run.state.pending
                        assert [dict(id=card_id(run.cards.create(name)), upgrade=modifier['upgrade_level'])
                                for name, modifier in zip(pending['offers'], pending['card_modifiers'])] == reward['cards']
                        if reward['index'] >= 0:
                            step(run, next(a for a in run.legal_actions() if isinstance(a, ChooseRewardCard)
                                           and a.definition_id == pending['offers'][reward['index']]
                                           and a.offer_index in (None, reward['index'])))
                step(run, LeaveRewards())
                assert run_boundary(run) == room['rewards']['state']
        elif room['kind'] == 'RestSiteRoom':
            step(run, Rest())
            step(run, LeaveRest())
        elif room['kind'] == 'TreasureRoom':
            step(run, LeaveTreasure())
        else:
            assert room['kind'] == 'MerchantRoom'
            step(run, LeaveShop())
        assert run_boundary(run) == room['state'], room['row']
    assert row['route'][-1]['combat']['encounter'] == 'VANTOM_BOSS'
    assert row['outcome'] == 'defeat' and run.state.phase is RunPhase.DEFEAT
    assert run_boundary(run) == row['state']
    assert not run.legal_actions()
