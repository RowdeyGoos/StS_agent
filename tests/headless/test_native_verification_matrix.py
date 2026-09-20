"""The grouped rerun binds fresh native executions to unchanged retained results."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_verification_final_2026_09_20.json').read_text())


def test_consolidated_native_matrix_matches_retained_results():
    assert {r['mode'] for r in RECORD['runs']} == {
        'queue', 'death-draw', 'attack-hooks', 'multiple-deaths', 'enemy-turn',
        'autoplay', 'autoplay-flak', 'draw-cards', 'remaining-draw', 'interactions',
        'enemy-interactions', 'death-start', 'end-boundary', 'reward-handoff',
        'campaign', 'generated-start',
    }
    for run in RECORD['runs']:
        assert run['exitCode'] == 0 and run['userDirectoryRemoved']
        assert run['stderrBytes'] == 0 and run['resultMatchesRetained']
        raw = (ROOT / run['baseline']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == run['baselineSha256']
        result = json.loads(raw)['result']
        assert hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest() == run['resultSha256']
        assert len(result.get('rows', [])) == run['rows']


def test_new_native_fixtures_match_executed_behavior_sources():
    source = ROOT / 'tools/native_combat_oracle/queue_runtime'
    # Generated-start's extended source is bound by test_native_generated_route.
    for name in ('campaign.cs',):
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == RECORD['fixtureSources'][name]
