"""An explicitly boosted-HP native win, separate from ordinary game success."""
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
RECORD = json.loads((ROOT / 'docs/evidence/native_boosted_campaign_2026_09_20.json').read_text())


def test_boosted_fixture_matches_executed_sources():
    assert RECORD['userDirectoryRemoved']
    assert '1000000' in RECORD['result']['source']
    rerun = json.loads((ROOT / 'docs/evidence/native_event_campaign_regressions_2026_09_20.json').read_text())
    original = next(r for r in rerun['runs'] if r['mode'] == 'boosted-campaign')
    assert original['resultMatchesRetained']
    assert original['resultSha256'] == hashlib.sha256(json.dumps(RECORD['result'], sort_keys=True).encode()).hexdigest()
    for name, digest in rerun['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest


def test_boosted_three_act_native_victory_with_json_continuation():
    row, = RECORD['result']['rows']
    assert row['outcome'] == 'victory'
    assert len(row['route']) == 48
    assert {r['actIndex'] for r in row['route']} == {0, 1, 2}
    assert [r['room']['ancient'] for r in row['route'] if r['room']['kind'] == 'ActTransition'] == ['PAEL', 'NONUPEIPE']
    assert sum(len(r['room'].get('combat', {}).get('actions', [])) for r in row['route']) == 917
    assert sum(len(a.get('choiceIndices', [])) for r in row['route']
               for a in r['room'].get('combat', {}).get('actions', [])) == 3
    run = replay_route(row, boosted=True)
    assert run.state.phase is RunPhase.VICTORY
    assert len(run.state.completed_acts) == 2


def test_previous_ordering_and_thorns_schemas_reject_atomically():
    combat = CombatEngine()
    combat.reset()
    for engine, previous in [(combat, 'headless_combat_state_v36'),
                             (RunEngine.ironclad_run(), 'headless_run_state_v55')]:
        before = engine.snapshot()
        bad = deepcopy(before)
        bad['schema'] = previous
        with pytest.raises(ValueError):
            engine.restore(bad)
        assert engine.snapshot() == before
