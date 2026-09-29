"""Combat-task boundaries, public summaries, independent resets and baselines."""
from dataclasses import FrozenInstanceError, asdict
import json

import pytest

gym = pytest.importorskip('gymnasium')
np = pytest.importorskip('numpy')
from gymnasium.utils.env_checker import check_env

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.gym_env import EnvironmentFailure
from game.agent.headless import AdapterFault, HeadlessAdapter
from game.agent.recording import load_trajectory
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.evaluation import evaluate_baselines
from game.agent.training.scenarios import SCENARIOS, episode_seed
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.run.state import RunPhase


def fixture(seed, *, cards=('strike',), hp=40, enemy_hp=6, relics=('burning_blood',), potions=()):
    run = RunEngine(seed=seed, card_ids=cards, hp=hp, rng_profile='native', config=RunConfig())
    for name in relics:
        run.obtain_relic(name)
    for name in potions:
        add_potion(run.state, name)
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=enemy_hp), cards_per_turn=len(cards))
    return run


def act(env, kind, definition=None):
    public = env.public_state
    entities = {n.ref: n for n in f.walk(public.context) if n.ref}
    choice = next(a for a in public.candidates if a.kind == kind and
                  (definition is None or entities[a.subject].definition_id == definition))
    return env.step(public.candidates.index(choice))


def test_victory_reads_post_hook_hp_ends_before_rewards_and_never_reports_run_victory():
    run = fixture(3)
    combat = run.combat
    with CombatTrainingEnv(engine_factory=lambda seed: run, max_decisions=1) as env:
        env.reset(seed=0)
        obs, reward, terminated, truncated, info = act(env, 'play_card')
        assert (reward, terminated, truncated) == (1.0, True, False)
        assert combat.done and combat.winner == 'player' and combat.player.hp == 40
        assert run.combat is None and run.state.phase is RunPhase.REWARD
        assert run.state.hp == info['combat']['hp'] == 46  # Burning Blood AFTER disposal.
        assert info['combat']['outcome'] == 'victory'
        assert not run.state.pending['gold_claimed'] and not run.state.pending['card_resolved']
        assert info['outcome'] == c.to_dict(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop'))
        assert env.encoder.decode(obs) == env.public_state
        assert not obs['action_mask'].any()
        summary = env._adapter.combat_summary
        assert set(asdict(summary)) == {'schema', 'combat_ref', 'outcome', 'hp', 'max_hp', 'turn'}
        with pytest.raises(FrozenInstanceError):
            summary.hp = 999
        with pytest.raises(gym.error.ResetNeeded):
            env.step(0)


def test_summary_api_explicitly_requires_the_full_profile():
    adapter = HeadlessAdapter(fixture(3))
    with pytest.raises(ValueError, match='full_run_v2'):
        _ = adapter.combat_summary


@pytest.mark.parametrize('revival', [None, 'fairy_in_a_bottle', 'lizard_tail'])
def test_defeat_and_revival_follow_authoritative_engine_result(revival):
    run = fixture(3, hp=1, enemy_hp=40,
                  relics=('lizard_tail',) if revival == 'lizard_tail' else (),
                  potions=('fairy_in_a_bottle',) if revival == 'fairy_in_a_bottle' else ())
    combat = run.combat
    with CombatTrainingEnv(engine_factory=lambda seed: run) as env:
        env.reset(seed=0)
        obs, reward, terminated, truncated, info = act(env, 'end_turn')
        assert reward == 0.0 and not truncated
        if revival:
            assert not terminated and not combat.done
            assert info['combat']['outcome'] == 'ongoing'
            assert info['combat']['hp'] == combat.player.hp > 0
            assert obs['action_mask'].any() and info['outcome'] is None
        else:
            assert terminated and combat.done and combat.winner == 'enemy'
            assert info['combat']['hp'] == run.state.hp == 0
            assert info['combat']['outcome'] == 'defeat' and info['outcome']['kind'] == 'defeat'
            assert not obs['action_mask'].any()


@pytest.mark.parametrize('potion_child', [False, True])
def test_nested_card_and_potion_selections_stay_with_the_policy(potion_child):
    run = fixture(3, cards=('armaments', 'strike', 'defend'), enemy_hp=40,
                  potions=('gamblers_brew',) if potion_child else ())
    with CombatTrainingEnv(engine_factory=lambda seed: run) as env:
        env.reset(seed=0)
        _, reward, done, cut, info = act(env, 'use_potion' if potion_child else 'play_card',
                                       None if potion_child else 'armaments')
        assert reward == 0.0 and not done and not cut
        assert any(n.kind == 'selection' for n in f.walk(env.public_state.context))
        before = run.snapshot()
        assert env.public_state == env._frame.decision and run.snapshot() == before
        assert any(a.kind == 'select_card' for a in env.public_state.candidates)
        _, reward, done, cut, _ = act(env, 'select_card')
        assert not done and not cut and reward == 0.0
        if any(a.kind == 'confirm_selection' for a in env.public_state.candidates):
            act(env, 'confirm_selection')
        assert run.combat is not None and run.combat.player.rules.selection is None
        assert not any(n.kind == 'selection' for n in f.walk(env.public_state.context))


def test_nested_selector_cutoff_preserves_successor_and_option_defaults():
    with CombatTrainingEnv(engine_factory=lambda seed: fixture(seed, cards=('armaments', 'strike', 'defend'),
                                                               enemy_hp=40)) as env:
        env.reset(seed=9, options={'max_decisions': 1})
        obs, reward, done, cut, info = act(env, 'play_card', 'armaments')
        assert (reward, done, cut) == (0.0, False, True)
        assert info['outcome']['reason'] == 'decision_budget'
        assert info['combat']['outcome'] == 'ongoing'
        assert obs['action_mask'].any()
        public = env.encoder.decode(obs)
        assert any(n.kind == 'selection' for n in f.walk(public.context))
        assert isinstance(env.public_state, f.PublicDecision)
        env.reset(seed=9)
        assert not act(env, 'play_card', 'armaments')[3]
        with pytest.raises(ValueError):
            env.reset(options={'stop_at_map': True})


def test_time_cutoff_keeps_cached_decision_and_never_dispatches(monkeypatch):
    clock = [50.0]
    monkeypatch.setattr('game.agent.gym_env.time.monotonic', lambda: clock[0])
    with CombatTrainingEnv(engine_factory=fixture, time_limit_seconds=1) as env:
        obs, _ = env.reset(seed=0)
        before = env._adapter._engine.snapshot()
        clock[0] += 2
        returned, reward, done, cut, info = env.step(0)
        assert all(np.array_equal(value, returned[key]) for key, value in obs.items())
        assert env._adapter._engine.snapshot() == before
        assert (reward, done, cut) == (0.0, False, True)
        assert info['execution'] is None and info['outcome']['reason'] == 'time_budget'


def test_invalid_and_stale_actions_never_advance_task():
    with CombatTrainingEnv(engine_factory=fixture, max_decisions=1) as env:
        obs, _ = env.reset(seed=0)
        original = env._adapter._engine.snapshot()
        for bad in (True, -1, 2048, 1.5):
            returned, reward, done, cut, info = env.step(bad)
            assert all(np.array_equal(value, returned[key]) for key, value in obs.items())
            assert (reward, done, cut) == (0.0, False, False)
            assert info['execution']['reason'] == 'invalid_action' and env._steps == 0
            assert env._adapter._engine.snapshot() == original
        env._adapter._engine.combat.player.energy += 1
        _, reward, done, cut, info = env.step(0)
        assert info['execution']['reason'] == 'stale_decision' and env._steps == 0
        assert (reward, done, cut) == (0.0, False, False)


def test_uncertain_mutation_latches_failure_until_reset(monkeypatch):
    with CombatTrainingEnv(engine_factory=fixture) as env:
        env.reset(seed=0)
        run = env._adapter._engine
        def fail(command):
            run.combat.player.hp -= 1
            raise RuntimeError('deliberate failure after mutation')
        monkeypatch.setattr(run, 'apply', fail)
        with pytest.raises(AdapterFault):
            act(env, 'play_card')
        with pytest.raises(EnvironmentFailure, match='reset_required'):
            env.step(0)
        with pytest.raises(AdapterFault):
            _ = env._adapter.combat_summary
        env.reset(seed=0)
        assert act(env, 'play_card')[2]


def test_escaping_enemy_uses_engine_outcome():
    def hopper(seed):
        run = RunEngine(seed=seed, config=RunConfig(), card_ids=('strike',), rng_profile='native')
        run.start_combat(encounter_id='hive_thieving_hopper', cards_per_turn=0)
        return run
    with CombatTrainingEnv(engine_factory=hopper) as env:
        env.reset(seed=0)
        combat = env._adapter._engine.combat
        for _ in range(5):
            _, _, done, cut, info = act(env, 'end_turn')
            if done or cut:
                break
        assert combat.enemies[0].escaped and combat.done and combat.winner == 'player'
        assert done and not cut and info['combat']['outcome'] == 'victory'


def test_enemy_revival_and_delayed_resolution_do_not_end_the_task():
    from game.headless.monsters.glory_bosses import TestSubject as Subject
    def subject(seed):
        run = RunEngine(seed=seed, config=RunConfig(), card_ids=('strike',), rng_profile='native')
        run.start_combat(encounter_factory=lambda rng: [Subject(rng)])
        run.combat.enemies[0].hp = 1  # Explicit controlled pre-attachment setup.
        return run
    with CombatTrainingEnv(engine_factory=subject) as env:
        env.reset(seed=0)
        combat = env._adapter._engine.combat
        _, reward, done, cut, info = act(env, 'play_card')
        assert combat.enemies[0].reviving and not combat.done
        assert (reward, done, cut) == (0.0, False, False)
        assert info['combat']['outcome'] == 'ongoing'
        act(env, 'end_turn')
        assert combat.enemies[0].hp > 0 and not env._done


def test_fatal_effects_set_final_max_hp_before_terminal_summary():
    run = fixture(3, cards=('feed',), hp=40)
    with CombatTrainingEnv(engine_factory=lambda seed: run) as env:
        env.reset(seed=0)
        _, reward, done, cut, info = act(env, 'play_card')
        assert (reward, done, cut) == (1.0, True, False)
        # Feed increases both current/max HP, followed by Burning Blood.
        assert info['combat']['max_hp'] == run.state.max_hp == 83
        assert info['combat']['hp'] == run.state.hp == 49


def test_scenarios_seed_splits_determinism_and_independent_episodes():
    schedules = [{episode_seed(split, i) for i in range(100)} for split in ('train', 'validation', 'test')]
    assert not schedules[0] & schedules[1] and not schedules[0] & schedules[2] and not schedules[1] & schedules[2]
    for item in SCENARIOS:
        run = item.make(3)
        assert run.state.rng.native and run.state.config.ascension == 0
        assert run.state.hp == run.state.max_hp == 80 and len(run.state.deck) == 10
        assert [r.definition_id for r in run.state.relics] == ['burning_blood']
        assert all(p is None for p in run.state.potions)
        assert all(c.upgrade_level == 0 for c in run.state.deck)
    with CombatTrainingEnv(max_decisions=12) as first, CombatTrainingEnv(max_decisions=12) as second:
        check_env(first, skip_render_check=True)
        first.reset(seed=42)
        second.reset(seed=42)
        original = second._adapter._engine.snapshot()
        trace = []
        for _ in range(12):
            a, b = first.public_state, second.public_state
            assert f.dumps(a) == f.dumps(b)
            choice = choose_action(a)
            index = a.candidates.index(choice)
            result = first.step(index)
            if not trace:
                assert second._adapter._engine.snapshot() == original
            other = second.step(index)
            assert result[1:] == other[1:]
            trace.append(f.dumps(a))
            if result[2] or result[3]:
                break
        first.reset(seed=42)
        assert f.dumps(first.public_state) == trace[0]
        assert not {'seed', 'rng', 'scenario', 'scenario_index'} & set(first._info())


def test_baseline_report_pairs_cases_records_canonical_rewards_and_private_replay(tmp_path):
    path, report = evaluate_baselines(output_dir=tmp_path/'public', cases_per_scenario=1,
                                      encounters=('overgrowth_nibbit',), max_decisions=64)
    assert json.loads(path.read_text()) == report
    assert report['status'] == 'complete' and report['unattempted_episodes'] == 0
    rows = report['episodes']
    assert len(rows) == 2 and rows[0]['pair_id'] == rows[1]['pair_id']
    for row in rows:
        trajectory = load_trajectory(path.parent/row['trajectory'], split='validation')
        assert all(t.reward == 0 for t in trajectory.transitions)
        assert len(trajectory.transitions) == row['steps']
        assert row['timings']['encoding_seconds'] > 0 and row['timings']['recording_seconds'] > 0
        assert trajectory.metadata.evidence == 'controlled_fixture'
    audits = list((tmp_path/'public-private').glob('*.audit.json'))
    assert len(audits) == 2 and all(a.stat().st_mode & 0o077 == 0 for a in audits)
    assert len({json.loads(a.read_text())['config']['seed'] for a in audits}) == 1
    assert 'policy_seed' not in path.read_text() and '"seed"' not in path.read_text()
    with pytest.raises(FileExistsError):
        evaluate_baselines(output_dir=path.parent, cases_per_scenario=1)


def test_failed_baseline_stops_without_publishing_partial_episode(tmp_path, monkeypatch):
    def fail(self, action):
        raise EnvironmentFailure('controlled_failure')
    monkeypatch.setattr(CombatTrainingEnv, 'step', fail)
    path, report = evaluate_baselines(output_dir=tmp_path/'public', cases_per_scenario=1)
    assert report['status'] == 'failed' and report['unattempted_episodes'] == 11
    assert report['summary']['random_legal']['failures'] == 1
    assert report['summary']['random_legal']['attempted'] == 1
    assert report['summary']['random_legal']['win_rate'] == 0.0
    assert len(list(path.parent.glob('*.trajectory.jsonl.partial'))) == 1
    assert not list(path.parent.glob('*.trajectory.jsonl'))


@pytest.mark.parametrize('factory', [lambda seed: RunEngine(seed=seed),
                                     lambda seed: RunEngine(seed=seed, hp=0)])
def test_reset_requires_a_live_owned_combat(factory):
    with CombatTrainingEnv(engine_factory=factory) as env:
        with pytest.raises(EnvironmentFailure, match='combat_start_required'):
            env.reset(seed=0)
