"""Full native solo victories, with JSON continuation for every replay command."""
import gzip
import json
from pathlib import Path

import pytest

from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize('character', ['silent', 'regent', 'necrobinder', 'defect'])
@pytest.mark.parametrize('ascension', [0, 10])
def test_native_character_campaign(character, ascension):
    path = ROOT / f'docs/evidence/native_campaign_{character}_a{ascension}_2026_09_21.json.gz'
    evidence = json.loads(gzip.decompress(path.read_bytes()))
    assert evidence['userDirectoryRemoved']
    from tests.headless.native_fixture_sources import assert_campaign_sources
    assert_campaign_sources(evidence)
    presentation = evidence['result']['presentation']
    assert presentation['cleared'] and presentation['listenersRemoved']
    row, = evidence['result']['rows']
    assert row['character'] == character and row['ascension'] == ascension
    assert row['outcome'] == 'victory'
    assert row['firstAct'] == ('underdocks' if ascension else 'overgrowth')
    rooms = [entry['room'] for entry in row['route']]
    assert len(rooms) == (49 if ascension else 48)
    assert sum(room['kind'] == 'ActTransition' for room in rooms) == 2
    assert sum('combat' in room for room in rooms) == (27 if ascension else 26)
    assert rooms[-1]['kind'] == 'Victory' and rooms[-1]['recorded']
    # Counters and every pile are captured at A0 as well as A10, together with
    # Stars, Osty, active orb values/capacity and player powers.
    for room in rooms:
        assert 'rngCounters' in room['state']
        if 'combat' in room:
            for state in [room['combat']['initial'], *[a['state'] for a in room['combat']['actions'] if a['state']]]:
                assert {'resources', 'piles', 'rngCounters'} <= state.keys()
    assert replay_route(row, boosted=True).state.phase is RunPhase.VICTORY
