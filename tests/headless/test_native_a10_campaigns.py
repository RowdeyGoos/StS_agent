"""Native A10 wins from both first acts, with full JSON continuation replay."""
import hashlib
import json
from pathlib import Path

import pytest

from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize('case,combats,actions', [('overgrowth_1', 25, 737), ('underdocks_4', 27, 767)])
def test_native_a10_campaign_with_json_continuation(case, combats, actions):
    evidence = json.loads((ROOT / f'docs/evidence/native_a10_{case}_2026_09_20.json').read_text())
    assert evidence['userDirectoryRemoved']
    assert evidence['result']['presentation']['cleared']
    assert evidence['result']['presentation']['listenersRemoved']
    for name, digest in evidence['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest
    row, = evidence['result']['rows']
    assert row['ascension'] == 10 and row['outcome'] == 'victory'
    rooms = [r['room'] for r in row['route']]
    assert len(rooms) == 49
    assert sum('combat' in r for r in rooms) == combats
    assert sum(len(r.get('combat', {}).get('actions', [])) for r in rooms) == actions
    bosses = [r['room'] for r in row['route'] if r['actIndex'] == 2 and
              'BOSS' in r['room'].get('combat', {}).get('encounter', '')]
    assert {r['combat']['encounter'] for r in bosses} == {'QUEEN_BOSS', 'AEONGLASS_BOSS'}
    assert bosses[1]['row'] == bosses[0]['row'] + 1
    assert bosses[1]['entry']['hp'] == bosses[0]['state']['hp']
    assert all(not r['rewards']['claims'] for r in bosses)
    assert sum(r['kind'] == 'ActTransition' for r in rooms) == 2
    assert rooms[0]['entry']['hp'] == 800_000  # Native A2 Neow entry heal.
    run = replay_route(row, boosted=True)
    assert run.state.phase is RunPhase.VICTORY
