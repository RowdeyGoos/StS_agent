"""Continuous native Act 1 trace; every Python action also resumes from JSON."""
import hashlib
import json
from pathlib import Path
from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_generated_route_2026_09_20.json').read_text())
LEGACY = json.loads((ROOT / 'docs/evidence/native_generated_start_route_regression_2026_09_20.json').read_text())


def test_route_fixture_identity_and_first_combat_regression():
    rerun = json.loads((ROOT / 'docs/evidence/native_boss_campaign_regressions_2026_09_20.json').read_text())
    assert {r['mode'] for r in rerun['runs']} == {'generated-start', 'generated-route', 'boosted-campaign', 'boosted-coverage', 'boosted-kaiser'}
    for name, digest in rerun['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest
    for record in rerun['runs']:
        assert record['exitCode'] == record['stderrBytes'] == 0
        assert record['userDirectoryRemoved'] and record['resultMatchesRetained']
        raw = (ROOT / record['baseline']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record['baselineSha256']
        assert hashlib.sha256(json.dumps(json.loads(raw)['result'], sort_keys=True).encode()).hexdigest() == record['resultSha256']
    previous = json.loads((ROOT / 'docs/evidence/native_generated_start_verified_2026_09_20.json').read_text())
    assert LEGACY['result'] == previous['result']


def test_generated_route_matches_native_through_boss_defeat():
    row, = RECORD['result']['rows']
    assert len(row['route']) == 16
    assert sum(len(room.get('combat', {}).get('actions', [])) for room in row['route']) == 170
    run = replay_route(row)
    assert row['route'][-1]['combat']['encounter'] == 'VANTOM_BOSS'
    assert row['outcome'] == 'defeat' and run.state.phase is RunPhase.DEFEAT
