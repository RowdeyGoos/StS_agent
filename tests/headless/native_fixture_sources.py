"""Bind retained results to explicit native reruns of the current harness."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
REPORT = ROOT / 'docs/evidence/native_character_campaign_regressions_2026_09_21.json'


def assert_current_sources():
    report = json.loads(REPORT.read_text())
    for name, digest in report['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest
    assert len(report['runs']) == 15
    for row in report['runs']:
        raw = (ROOT / row['baseline']).read_bytes()
        baseline = json.loads(gzip.decompress(raw) if row['baseline'].endswith('.gz') else raw)
        assert hashlib.sha256(raw).hexdigest() == row['baselineSha256']
        assert hashlib.sha256(json.dumps(baseline['result'], sort_keys=True).encode()).hexdigest() == row['resultSha256']
        assert row['resultMatchesRetained'] and row['userDirectoryRemoved']
        assert row['exitCode'] == row['stderrBytes'] == 0
    return report


def assert_campaign_sources(capture):
    current = assert_current_sources()
    # These modules changed across the retained item probes / character work.
    # Their original hashes remain historical; the report binds fresh executions
    # of every retained campaign mode to the current sources and equal results.
    changed = {'death_draw.cs', 'item_status.cs', 'character.cs', 'generated_start.cs', 'Oracle.cs', 'run.py'}
    for name, digest in capture['fixtureSources'].items():
        if name not in changed:
            assert current['fixtureSources'][name] == digest
    if 'result' in capture:
        digest = hashlib.sha256(json.dumps(capture['result'], sort_keys=True).encode()).hexdigest()
        assert any(row['resultSha256'] == digest for row in current['runs'])
    if 'runs' in capture:
        assert {row['baseline'] for row in capture['runs']} <= {row['baseline'] for row in current['runs']}
