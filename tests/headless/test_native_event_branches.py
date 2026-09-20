"""All declared solo event families against retained native branch captures."""
import gzip
import hashlib
import json
from pathlib import Path
import re

import pytest
from game.headless.events.catalog import EVENTS
from game.headless.relics.base import RELICS
from game.headless.cards.extended_events import RIDERS
from tests.headless.native_event_replay import replay

ROOT = Path(__file__).parents[2]
DIRECTORY = ROOT / 'docs/evidence/native_event_branches_2026_09_20'
MANIFEST = json.loads((DIRECTORY / 'manifest.json').read_text())
ENTRIES = MANIFEST['events']


def capture(entry):
    packed = (DIRECTORY / entry['file']).read_bytes()
    assert hashlib.sha256(packed).hexdigest() == entry['compressedSha256']
    raw = gzip.decompress(packed)
    assert hashlib.sha256(raw).hexdigest() == entry['rawSha256']
    result = json.loads(raw)
    assert result['userDirectoryRemoved']
    assert result['fixtureSources'] == MANIFEST['fixtureSources']
    assert len(result['result']['rows']) == entry['cases']
    return result['result']['rows']


@pytest.mark.parametrize('entry', ENTRIES, ids=lambda entry: entry['event'])
def test_native_solo_event_branch_matrix(entry):
    cache = {}
    for row in capture(entry):
        try:
            replay(row, cache)
        except Exception as error:
            raise AssertionError(f"{row['eventName']} seed={row['seed']} A{row['ascension']} enhanced={row['enhanced']} variant={row['variant']} selector={row['selectionVariant']} path={row['path']}") from error


def test_native_event_roster_and_all_ancient_offers_are_present():
    names = {re.sub(r'(?<!^)(?=[A-Z])', '_', row['event']).lower() for row in ENTRIES}
    assert names | {'the_architect'} == set(EVENTS) | {'neow'}
    ancient_names = {'Neow','Darv','Nonupeipe','Orobas','Pael','Tanx','Tezcatara','Vakuu'}
    offers = {name.lower() for row in ENTRIES if row['event'] in ancient_names for name in row['choices']}
    assert offers == {name for name, relic in RELICS.items() if relic.rarity == 'ancient'}
    assert len(offers) == 99
    assert sum(row['cases'] for row in ENTRIES) == MANIFEST['cases']
    rows = capture(next(e for e in ENTRIES if e['event'] == 'TinkerTime'))
    outcomes = {(c['eventData']['kind'], c['eventData']['rider']) for row in rows
                for c in row['state']['deck'] if c['eventData']}
    assert outcomes == {(kind, rider) for kind, riders in RIDERS.items() for rider in riders}
    trial = next(e for e in ENTRIES if e['event'] == 'Trial')
    for defendant in ('MERCHANT', 'NOBLE', 'NONDESCRIPT'):
        assert {f'TRIAL.pages.{defendant}.options.GUILTY', f'TRIAL.pages.{defendant}.options.INNOCENT'} <= set(trial['choices'])
    repy = capture(next(e for e in ENTRIES if e['event'] == 'WarHistorianRepy'))
    assert {sum(c['id'] == 'LANTERN_KEY' for c in r['before']['deck']) for r in repy} == {0,1,2}
    for row in repy:
        if len(row['path']) == 1:
            assert row['finished'] == (row['variant'] != 0)
    rows = capture(next(e for e in ENTRIES if e['event'] == 'Neow'))
    assert {s['selected'] for row in rows for trace in row['trace'] for s in trace['selections'] if s['kind'] == 'bundle'} == {0,1}


def test_current_harness_and_unchanged_native_campaigns_are_bound():
    source = ROOT / 'tools/native_combat_oracle/queue_runtime'
    for name, digest in MANIFEST['fixtureSources'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    report = json.loads((ROOT / 'docs/evidence/native_event_branch_regressions_2026_09_20.json').read_text())
    assert report['fixtureSources'] == MANIFEST['fixtureSources']
    assert len(report['runs']) == 13
    assert {'campaign','reward-handoff','event-inventory'} <= {r['mode'] for r in report['runs']}
    for row in report['runs']:
        raw = (ROOT / row['baseline']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['baselineSha256']
        assert hashlib.sha256(json.dumps(json.loads(raw)['result'], sort_keys=True).encode()).hexdigest() == row['resultSha256']
        assert row['resultMatchesRetained'] and row['userDirectoryRemoved']
        assert row['exitCode'] == row['stderrBytes'] == 0
