"""Boosted native campaign through Soul Fysh, Kaiser Crab and Test Subject."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game.headless.core.combat import CombatEngine
from game.headless.core.native_rng import NativeRng
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_boosted_kaiser_2026_09_20.json').read_text())


def test_kaiser_fixture_identity_and_presentation_cleanup():
    assert RECORD['userDirectoryRemoved']
    assert RECORD['spineExtensionSha256'] == 'dde5c7682eb29f3c69e4191f6361a1f0731292188b2603bee02adf726abde0d8'
    assert RECORD['result']['presentation'] == dict(
        armsAttached=2, armDeaths=2, nexusDeaths=1, cleared=True, listenersRemoved=True)
    rerun = json.loads((ROOT / 'docs/evidence/native_a10_campaign_regressions_2026_09_20.json').read_text())
    row = next(r for r in rerun['runs'] if r['mode'] == 'boosted-kaiser')
    assert row['resultMatchesRetained'] and row['exitCode'] == row['stderrBytes'] == 0
    assert row['resultSha256'] == hashlib.sha256(json.dumps(RECORD['result'], sort_keys=True).encode()).hexdigest()
    for name, digest in rerun['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest


def test_native_kaiser_three_act_victory_with_json_continuation():
    row, = RECORD['result']['rows']
    assert row['firstAct'] == 'underdocks' and row['seed'] == '0'
    assert row['outcome'] == 'victory' and len(row['route']) == 48
    rooms = [r['room'] for r in row['route']]
    assert [r['combat']['encounter'] for r in rooms if 'BOSS' in r.get('combat', {}).get('encounter', '')] == [
        'SOUL_FYSH_BOSS', 'KAISER_CRAB_BOSS', 'TEST_SUBJECT_BOSS']
    assert sum(len(r.get('combat', {}).get('actions', [])) for r in rooms) == 712
    cookie = next(r for r in rooms if r.get('choice') == 'YUMMY_COOKIE')
    assert cookie['upgradeDeckIndices'] == [0, 1, 2, 3]
    assert all(c['upgrade'] == 1 for c in cookie['state']['deck'][:4])
    crab = next(r['combat'] for r in rooms if r.get('combat', {}).get('encounter') == 'KAISER_CRAB_BOSS')
    assert any(e['block'] >= 99 for a in crab['actions'] if a['state'] for e in a['state']['enemies'])
    run = replay_route(row, boosted=True)
    assert run.state.phase is RunPhase.VICTORY


def test_beckon_native_position_counts_from_draw_top():
    run = RunEngine(seed=7, rng_profile='native', max_hp=1000, card_ids=['strike'] * 8)
    run.start_combat(encounter_id='underdocks_soul_fysh', cards_per_turn=0)
    player = run.combat.player
    before = list(player.deck.draw_pile)
    assert len(before) == 8
    player.deck.rng = NativeRng(0)  # Native seed 0's first NextInt(9) is 5.
    enemy = run.combat.enemies[0]
    enemy.after_move(player, enemy.intent)
    beckon = player.deck.draw_pile[3]
    assert beckon.definition.definition_id == 'beckon'
    assert player.deck.draw_pile == before[:3] + [beckon] + before[3:]
    assert [c.definition.definition_id for c in player.deck.discard_pile] == ['beckon']
    assert player.deck.rng.counter == 1


def test_previous_beckon_continuation_versions_reject_atomically():
    combat = CombatEngine()
    combat.reset()
    for engine, old in [(combat, 'headless_combat_state_v38'),
                        (RunEngine.ironclad_run(), 'headless_run_state_v57')]:
        before = engine.snapshot()
        bad = deepcopy(before)
        bad['schema'] = old
        with pytest.raises(ValueError):
            engine.restore(bad)
        assert engine.snapshot() == before


@pytest.mark.parametrize('supply_library', [False, True])
def test_kaiser_runner_rejects_missing_or_unpinned_extension_before_build(tmp_path, monkeypatch, supply_library):
    import runpy
    import subprocess
    import sys
    module = runpy.run_path(str(ROOT / 'tools/native_combat_oracle/queue_runtime/run.py'))
    output = tmp_path / 'output'
    args = ['run.py', '--mode', 'boosted-kaiser']
    for name in ('engine', 'native-data', 'godot-sdk', 'godot-generators', 'dotnet'):
        args += ['--' + name, str(tmp_path / name)]
    args += ['--output', str(output)]
    if supply_library:
        library = tmp_path / 'wrong-library'
        library.write_bytes(b'not the pinned native extension')
        args += ['--spine-extension', str(library)]
    monkeypatch.setattr(sys, 'argv', args)
    def unexpected_process(*args, **kwargs):
        pytest.fail('Invalid presentation input must not build or launch a process.')
    monkeypatch.setattr(subprocess, 'run', unexpected_process)
    with pytest.raises(SystemExit) as error:
        module['main']()
    assert error.value.code == 2
    assert not output.exists()
