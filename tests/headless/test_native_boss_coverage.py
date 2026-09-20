"""All regional bosses in native boosted campaigns, with JSON at every action."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game.headless.core.combat import CombatEngine
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]
CASES = ('overgrowth_1', 'overgrowth_3', 'underdocks_4')


def record(case):
    return json.loads((ROOT / f'docs/evidence/native_boosted_{case}_2026_09_20.json').read_text())


@pytest.mark.parametrize('case,combats,actions', zip(CASES, (26, 28, 27), (618, 700, 600)))
def test_remaining_boss_campaign_with_json_continuation(case, combats, actions):
    evidence = record(case)
    assert evidence['userDirectoryRemoved']
    assert evidence['result']['presentation']['cleared']
    assert evidence['result']['presentation']['listenersRemoved']
    rerun = json.loads((ROOT / 'docs/evidence/native_item_status_regressions_2026_09_20.json').read_text())
    fresh = next(r for r in rerun['runs'] if r.get('case') == case.replace('_', '-') and r['ascension'] == 0)
    assert fresh['userDirectoryRemoved'] and fresh['resultMatchesRetained']
    assert fresh['exitCode'] == fresh['stderrBytes'] == 0
    assert hashlib.sha256(json.dumps(evidence['result'], sort_keys=True).encode()).hexdigest() == fresh['resultSha256']
    from tests.headless.native_fixture_sources import assert_campaign_sources
    assert_campaign_sources(rerun)
    row, = evidence['result']['rows']
    rooms = [r['room'] for r in row['route']]
    assert row['outcome'] == 'victory' and len(rooms) == 48
    assert sum('combat' in r for r in rooms) == combats
    assert sum(len(r.get('combat', {}).get('actions', [])) for r in rooms) == actions
    run = replay_route(row, boosted=True)
    assert run.state.phase is RunPhase.VICTORY


def test_retained_native_campaigns_cover_every_regional_boss():
    records = [record(case) for case in (*CASES, 'campaign', 'underdocks', 'kaiser')]
    bosses = {r['room']['combat']['encounter'] for data in records
              for row in data['result']['rows'] for r in row['route']
              if 'BOSS' in r['room'].get('combat', {}).get('encounter', '')}
    assert bosses == {'VANTOM_BOSS', 'CEREMONIAL_BEAST_BOSS', 'THE_KIN_BOSS',
                      'LAGAVULIN_MATRIARCH_BOSS', 'SOUL_FYSH_BOSS', 'WATERFALL_GIANT_BOSS',
                      'KNOWLEDGE_DEMON_BOSS', 'THE_INSATIABLE_BOSS', 'KAISER_CRAB_BOSS',
                      'TEST_SUBJECT_BOSS', 'AEONGLASS_BOSS', 'QUEEN_BOSS'}
    rooms = [r['room'] for case in CASES for r in record(case)['result']['rows'][0]['route']]
    assert {r['eventId'] for r in rooms if r['kind'] == 'EventRoom'} == {
        'SUNKEN_STATUE', 'AMALGAMATOR', 'SLIPPERY_BRIDGE', 'TRASH_HEAP', 'COLOSSAL_FLOWER'}
    assert next(r for r in rooms if r.get('eventId') == 'AMALGAMATOR')['eventDeckIndices'] == [0, 1]
    assert any(r.get('restUpgradeDeckIndex') is not None for r in rooms)
    assert any(r.get('choice') == 'SEA_GLASS' for r in rooms)


def test_previous_boss_and_event_cursor_schemas_reject_atomically():
    combat = CombatEngine()
    combat.reset()
    for engine, old in [(combat, 'headless_combat_state_v39'),
                        (RunEngine.ironclad_run(), 'headless_run_state_v58')]:
        before = engine.snapshot()
        bad = deepcopy(before)
        bad['schema'] = old
        with pytest.raises(ValueError):
            engine.restore(bad)
        assert engine.snapshot() == before
