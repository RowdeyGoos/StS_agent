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
    active_case = None
    for row in capture(entry):
        case = (row['seed'], row['ascension'], row['enhanced'],
                row.get('variant', 0), row.get('selectionVariant', 0))
        if case != active_case:
            # Prefixes belong to one scenario. Retaining prior scenarios only
            # multiplies memory now that the cache actually stores every prefix.
            cache.clear()
            active_case = case
        try:
            replay(row, cache)
        except Exception as error:
            raise AssertionError(f"{row['eventName']} seed={row['seed']} A{row['ascension']} enhanced={row['enhanced']} variant={row['variant']} selector={row['selectionVariant']} path={row['path']}") from error


def test_replay_prefix_cache_reuses_parent_without_changing_result(monkeypatch):
    from tests.headless import native_event_replay
    rows = capture(next(e for e in ENTRIES if e['event'] == 'FakeMerchant'))[:2]
    assert rows[1]['path'][:-1] == rows[0]['path']
    expected = replay(rows[1]).snapshot()
    cache = {}
    replay(rows[0], cache)
    monkeypatch.setattr(native_event_replay, 'setup', lambda row: pytest.fail('Cached parent rebuilt'))
    assert replay(rows[1], cache).snapshot() == expected
    assert len(cache) == 2 and all(isinstance(key, tuple) for key in cache)


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
    # Original branch captures keep their own runner identity. Their event
    # implementations are unchanged; the current harness has a fresh rerun.
    for name, digest in MANIFEST['fixtureSources'].items():
        if name not in {'Oracle.cs', 'death_draw.cs', 'run.py', 'generated_start.cs'}:
            assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    report = json.loads((ROOT / 'docs/evidence/native_item_status_regressions_2026_09_20.json').read_text())
    from tests.headless.native_fixture_sources import assert_campaign_sources
    assert_campaign_sources(report)
    assert len(report['runs']) == 13
    assert {'campaign','reward-handoff','event-inventory'} <= {r['mode'] for r in report['runs']}
    for row in report['runs']:
        raw = (ROOT / row['baseline']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['baselineSha256']
        assert hashlib.sha256(json.dumps(json.loads(raw)['result'], sort_keys=True).encode()).hexdigest() == row['resultSha256']
        assert row['resultMatchesRetained'] and row['userDirectoryRemoved']
        assert row['exitCode'] == row['stderrBytes'] == 0
