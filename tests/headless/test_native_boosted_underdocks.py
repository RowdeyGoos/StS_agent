"""A continuous boosted native campaign with earned room and inventory actions."""
import hashlib
import json
from pathlib import Path

from game.headless.run.state import RunPhase
from tests.headless.native_route_replay import replay_route

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_boosted_underdocks_2026_09_20.json').read_text())


def test_expanded_boosted_fixture_matches_executed_sources():
    assert RECORD['userDirectoryRemoved']
    rerun = json.loads((ROOT / 'docs/evidence/native_item_status_regressions_2026_09_20.json').read_text())
    original = next(r for r in rerun['runs'] if r['mode'] == 'boosted-coverage')
    assert original['resultMatchesRetained']
    assert original['resultSha256'] == hashlib.sha256(json.dumps(RECORD['result'], sort_keys=True).encode()).hexdigest()
    from tests.headless.native_fixture_sources import assert_campaign_sources
    assert_campaign_sources(rerun)


def test_native_underdocks_three_act_victory_and_json_continuation():
    row, = RECORD['result']['rows']
    assert row['firstAct'] == 'underdocks' and row['seed'] == '1'
    assert row['outcome'] == 'victory' and len(row['route']) == 48
    rooms = [r['room'] for r in row['route']]
    assert sum(bool(r.get('purchases')) for r in rooms) >= 2
    assert sum(bool(r.get('chestClaim')) for r in rooms) == 2
    assert any(r.get('eventId') == 'SUNKEN_TREASURY' for r in rooms)
    assert any(a['kind'] == 'potion' for r in rooms for a in r.get('combat', {}).get('actions', []))
    run = replay_route(row, boosted=True)
    assert run.state.phase is RunPhase.VICTORY


def test_phial_holster_uses_native_combat_potion_stream_at_neow():
    from game.headless.run.engine import RunEngine
    from game.headless.run.ancient import PROFILE
    from game.headless.run.actions import ChooseAncientRelic
    run = RunEngine.ironclad_run(seed=1, first_act='underdocks', ancient_profile=PROFILE)
    before = run.state.rng.request_count('rewards')
    run.apply(ChooseAncientRelic('phial_holster'))
    assert [p.definition_id if p else None for p in run.state.potions] == ['weak_potion', 'skill_potion', None, None]
    assert run.state.rng.request_count('rewards') == before
    assert run.state.rng.request_count('combat_potion_generation') == 4


def test_cubex_setup_matches_native_block_command_boundary():
    from game.headless.core.combat import CombatEngine
    from game.headless.monsters.overgrowth_normal import CubexConstruct
    combat = CombatEngine(encounter_factory=lambda rng: [CubexConstruct(rng)])
    combat.reset()
    assert combat.enemies[0].block == 0
    assert combat.enemies[0].statuses.get('artifact') == 1
