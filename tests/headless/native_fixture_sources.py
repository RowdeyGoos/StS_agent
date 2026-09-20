"""Bind retained campaign implementations and the separately rerun probe harness."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).parents[2]


def assert_campaign_sources(capture):
    current=json.loads(gzip.decompress((ROOT/'docs/evidence/native_characters_2026_09_20.json.gz').read_bytes()))
    changed={'death_draw.cs','item_status.cs','character.cs','run.py'}
    for name,digest in capture['fixtureSources'].items():
        if name not in changed:
            assert current['fixtureSources'][name]==digest
    for name,digest in current['fixtureSources'].items():
        assert hashlib.sha256((ROOT/'tools/native_combat_oracle/queue_runtime'/name).read_bytes()).hexdigest()==digest
    # The runner only stages the new probe module. Its launch/safety/cleanup
    # behavior remains byte-identical to the retained campaign runner.
    runner=(ROOT/'tools/native_combat_oracle/queue_runtime/run.py').read_bytes()
    assert hashlib.sha256(runner.replace(b'"item_status.cs", "character.cs",',b'"item_status.cs",')).hexdigest()==capture['fixtureSources']['run.py']
    # Current shared-dispatcher execution reproduces the retained enemy turns.
    fresh=current['sharedDispatcherRegression']
    baseline=(ROOT/fresh['baseline']).read_bytes()
    assert fresh['fixtureSources']==current['fixtureSources'] and fresh['userDirectoryRemoved']
    assert hashlib.sha256(baseline).hexdigest()==fresh['baselineSha256']
    assert hashlib.sha256(json.dumps(json.loads(baseline)['result'],sort_keys=True).encode()).hexdigest()==fresh['resultSha256']
