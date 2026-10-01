"""Recorded task outcomes, offline conversion, atomic publication and game effects."""
import hashlib
import json
from dataclasses import dataclass, fields, replace
from pathlib import Path
import uuid

import pytest

gym = pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.dataset import training_examples as canonical_examples
from game.agent.encoding.full import FullRunEncoder
from game.agent.provenance import Implementation
from game.agent.recording import Metadata, load_trajectory
from game.agent.training.dataset import load_training_dataset, training_examples
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.records import CombatTrainingRecorder, load_training_episode
from game.agent.training.rewards import RewardSpec
from .test_combat_training import act, fixture

IDENTITY = Implementation('controlled-test', 'a'*64, 'b'*64, 'test-policy')


def metadata():
    return Metadata.create(IDENTITY, episode_id=uuid.uuid4().hex, scenario='controlled-test',
                           split='train', evidence='controlled_fixture')


def record(tmp_path, *, mode='win', spec=None, compressed=False):
    spec = spec or RewardSpec({'combat_loss': -1, 'win_hp_fraction': 0.25, 'end_turn_action': -0.01})
    path = tmp_path / (uuid.uuid4().hex + '.trajectory.jsonl' + ('.gz' if compressed else ''))
    def factory(seed):
        return fixture(seed, hp=1 if mode == 'loss' else 40, enemy_hp=6 if mode == 'win' else 100,
                       relics=() if mode == 'loss' else ('burning_blood',))
    with CombatTrainingEnv(engine_factory=factory, max_decisions=1, reward_spec=spec) as env:
        _, info = env.reset(seed=0)
        with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat'], reward_spec=spec) as writer:
            state = env.public_state
            action = next(a for a in state.candidates if a.kind == ('end_turn' if mode == 'loss' else 'play_card'))
            _, reward, done, cut, info = env.step(env.action_index(action))
            writer.append(action, c.from_dict(info['execution']), env.public_state,
                          combat_summary=info['combat'], reward=reward, terminated=done, truncated=cut)
            writer.finish(c.from_dict(info['outcome']), combat_summary=info['combat'], terminated=done, truncated=cut)
    return path, writer.path


@pytest.fixture
def pair(tmp_path):
    return record(tmp_path)


@pytest.mark.parametrize('mode,expected,done,cut', [('win', 1+0.25*46/80, True, False),
                                                 ('loss', -1.01, True, False), ('cutoff', 0, False, True)])
def test_task_and_canonical_records_keep_distinct_rewards_and_bootstrap_flags(tmp_path, mode, expected, done, cut):
    paths = record(tmp_path, mode=mode)
    episode = load_training_episode(*paths, split='train')
    step, = episode.transitions
    assert step.reward == pytest.approx(expected)
    assert (step.terminated, step.truncated) == (done, cut)
    assert (episode.ending.terminated, episode.ending.truncated) == (done, cut)
    canonical = episode.trajectory
    assert canonical.transitions[0].reward == 0
    assert canonical.sha256 == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    encoded, = training_examples([paths], split='train', encoder=FullRunEncoder())
    original, = canonical_examples([paths[0]], split='train', encoder=FullRunEncoder())
    assert (encoded.reward, encoded.terminated, encoded.truncated) == (step.reward, done, cut)
    assert original.reward == 0 and original.truncated == (mode != 'loss')
    assert encoded.successor['action_mask'].any() == cut
    assert encoded.reward_spec_id == episode.reward_spec.identity
    assert 'reward_spec_id' not in encoded.observation


@pytest.mark.parametrize('mode', ('win', 'loss', 'cutoff'))
@pytest.mark.parametrize('compressed', (False, True))
def test_incremental_finalization_remains_independently_loadable(tmp_path, monkeypatch, mode, compressed):
    import game.agent.training.records as records
    def forbidden(*args, **kwargs):
        pytest.fail('Finalization reparsed the completed public trajectory')
    with monkeypatch.context() as patch:
        patch.setattr(records, 'load_trajectory', forbidden)
        paths = record(tmp_path, mode=mode, compressed=compressed)
    episode = load_training_episode(*paths, split='train')
    assert len(episode.transitions) == 1
    assert episode.ending.combat.outcome == {'win':'victory', 'loss':'defeat', 'cutoff':'ongoing'}[mode]
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('compressed', (False, True))
@pytest.mark.parametrize('damage', ('changed_bytes', 'truncated'))
def test_incremental_finalization_checks_actual_stored_bytes(tmp_path, monkeypatch, compressed, damage):
    import gzip
    from game.agent.recording import TrajectoryWriter
    finish, published = TrajectoryWriter.finish, []
    def altered(writer, *args, **kwargs):
        result = finish(writer, *args, **kwargs)
        assert writer.completion is not None
        published.append(writer.path)
        data = writer.path.read_bytes()
        if damage == 'truncated':
            data = data[:-8]
        else:
            raw = gzip.decompress(data) if compressed else data
            raw = raw[:-1] + b' '  # Still valid JSON; different canonical bytes.
            data = gzip.compress(raw) if compressed else raw
        writer.path.write_bytes(data)
        return result
    monkeypatch.setattr(TrajectoryWriter, 'finish', altered)
    with pytest.raises(ValueError, match='digest|compressed'):
        record(tmp_path, compressed=compressed)
    assert len(published) == 1 and published[0].exists()
    assert not list(tmp_path.glob('*.training.json'))
    assert len(list(tmp_path.glob('*.training.json.partial'))) == 1


@pytest.mark.parametrize('phase', ('initial', 'successor'))
def test_recorder_checks_canonical_hud_in_structural_caller_records(tmp_path, phase):
    with CombatTrainingEnv(engine_factory=lambda seed: fixture(seed, enemy_hp=100), max_decisions=1) as env:
        _, info = env.reset(seed=0)
        def misleading(public):
            @dataclass
            class InputNode:
                kind: str
                definition_id: str
                ref: object
                fields: tuple
                links: tuple
                children: tuple
                def get(self, key, default=None):
                    return public.run.get(key, default)
            values = {field.name: getattr(public.run, field.name) for field in fields(f.Node)}
            values['fields'] = tuple(replace(field, value=field.value+1) if field.key == 'hp' else field
                                     for field in public.run.fields)
            return replace(public, run=InputNode(**values))
        path = tmp_path/'structural.trajectory.jsonl'
        if phase == 'initial':
            with pytest.raises(ValueError, match='HUD'):
                CombatTrainingRecorder(path, metadata(), misleading(env.public_state), info['combat'])
        else:
            with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat']) as writer:
                action = next(a for a in env.public_state.candidates if a.kind == 'play_card')
                _, reward, done, cut, info = env.step(env.action_index(action))
                with pytest.raises(ValueError, match='HUD'):
                    writer.append(action, c.from_dict(info['execution']), misleading(env.public_state),
                                  combat_summary=info['combat'], reward=reward, terminated=done, truncated=cut)
        assert not path.exists() and not list(tmp_path.glob('*.training.json'))


def test_explicit_offline_conversion_and_mixed_spec_preflight_before_first_sample(tmp_path, pair):
    other = record(tmp_path, spec=RewardSpec())
    iterator = load_training_dataset([pair, other], split='train')
    with pytest.raises(ValueError, match='Mixed reward'):
        next(iterator)
    originals = [p.read_bytes() for paths in (pair, other) for p in paths]
    conversion = RewardSpec({'combat_win': 0, 'win_hp_fraction': 1})
    converted = list(load_training_dataset([pair, other], split='train', reward_spec=conversion))
    assert len({e.reward_spec.identity for e in converted}) == 1
    assert len({e.recorded_spec.identity for e in converted}) == 2
    assert all(e.transitions[0].reward == 46/80 for e in converted)
    assert originals == [p.read_bytes() for paths in (pair, other) for p in paths]
    with pytest.raises(ValueError, match='split'):
        load_training_episode(*pair, split='test')


@pytest.mark.parametrize('edit', [
    lambda v: v.update(schema='sts_combat_training_v99'),
    lambda v: v.update(task='full_run'), lambda v: v.update(seed=123),
    lambda v: v.update(trajectory_sha256='0'*64), lambda v: v.update(episode_id='0'*32),
    lambda v: v.update(reward_spec_id='other-objective'),
    lambda v: v['reward_spec']['weights'].update(combat_win=99),
    lambda v: v['transitions'].append(v['transitions'][0]),
    lambda v: v.update(transitions=[]),
    lambda v: v['transitions'][0].update(index=True),
    lambda v: v['transitions'][0].update(index=1),
    lambda v: v['transitions'][0].update(reward=1),
    lambda v: v['transitions'][0].update(reward=True),
    lambda v: v['transitions'][0]['components'].pop('potion_use_action'),
    lambda v: v['transitions'][0]['components'].update(end_turn_action=1),
    lambda v: v['transitions'][0]['combat'].update(seed=1),
    lambda v: v['transitions'][0]['combat'].update(combat_ref='combat:999'),
    lambda v: v['transitions'][0]['combat'].update(hp=999),
    lambda v: v['initial_combat'].update(hp=39),
    lambda v: v['initial_combat'].update(turn=2),
    lambda v: v['transitions'][0].update(terminated=False, truncated=True),
    lambda v: v['transitions'][0].update(terminated=True, truncated=True),
    lambda v: v['ending'].update(terminated=False, truncated=True),
    lambda v: v['ending']['combat'].update(outcome='ongoing'),
])
def test_corrupt_missing_duplicate_or_incompatible_sidecars_reject(pair, edit):
    value = json.loads(pair[1].read_text())
    edit(value)
    pair[1].write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_training_episode(*pair, split='train', reward_spec=RewardSpec())


def test_cutoff_cannot_be_relabelled_a_success_even_with_consistent_components(tmp_path):
    paths = record(tmp_path, mode='cutoff')
    value = json.loads(paths[1].read_text())
    row = value['transitions'][0]
    row.update(terminated=True, truncated=False)
    row['combat']['outcome'] = 'victory'
    row['components'].update(combat_win=1, win_hp_fraction=row['combat']['hp']/row['combat']['max_hp'])
    row['reward'] = RewardSpec.from_dict(value['reward_spec']).evaluate(row['components'])
    value['ending'] = {k: row[k] for k in ('terminated', 'truncated', 'combat')}
    paths[1].write_text(json.dumps(value))
    with pytest.raises(ValueError, match='canonical trajectory'):
        load_training_episode(*paths, split='train')


def test_digest_covers_canonical_footer_and_sidecar_parser_rejects_ambiguity(tmp_path, pair):
    paths = record(tmp_path, mode='cutoff')
    source = paths[0].read_bytes()
    # The legacy footer hashes only its prefix; this is still a valid canonical
    # file, but must not join the sidecar produced for the original endpoint.
    paths[0].write_bytes(source.replace(b'"reason":"decision_budget"', b'"reason":"time_budget"'))
    load_trajectory(paths[0])
    with pytest.raises(ValueError, match='digest'):
        load_training_episode(*paths, split='train')
    original = pair[1].read_text()
    for bad in (original.replace('"schema":', '"schema":"other","schema":', 1),
                original.replace('"reward":1.14375', '"reward":NaN'), original[:-5]):
        pair[1].write_text(bad)
        with pytest.raises(ValueError):
            load_training_episode(*pair, split='train')


@pytest.mark.parametrize('after_action', [False, True])
@pytest.mark.parametrize('compressed', [False, True])
def test_pre_dispatch_timeout_has_no_fake_transition_or_extra_reward(tmp_path, monkeypatch, after_action, compressed):
    clock = [1.0]
    monkeypatch.setattr('game.agent.gym_env.time.monotonic', lambda: clock[0])
    path = tmp_path / ('timeout.trajectory.jsonl' + ('.gz' if compressed else ''))
    with CombatTrainingEnv(engine_factory=lambda seed: fixture(seed, enemy_hp=100), time_limit_seconds=1,
                           reward_spec=RewardSpec({'end_turn_action': -0.25})) as env:
        _, info = env.reset(seed=0)
        with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat'],
                                     reward_spec=env.reward_spec) as writer:
            if after_action:
                state = env.public_state
                action = next(a for a in state.candidates if a.kind == 'end_turn')
                _, reward, done, cut, info = env.step(env.action_index(action))
                writer.append(action, c.from_dict(info['execution']), env.public_state,
                              combat_summary=info['combat'], reward=reward, terminated=done, truncated=cut)
            clock[0] += 2
            _, reward, done, cut, info = env.step(0)
            assert reward == 0 and info['execution'] is info['training_reward'] is None
            writer.finish(c.from_dict(info['outcome']), combat_summary=info['combat'], terminated=done, truncated=cut)
    episode = load_training_episode(path, writer.path, split='train')
    assert len(episode.transitions) == int(after_action)
    assert sum(t.reward for t in episode.transitions) == (-0.25 if after_action else 0)
    assert episode.ending.truncated and not episode.ending.terminated
    if after_action:
        assert episode.transitions[-1].truncated


def test_sidecar_publication_failure_keeps_canonical_and_partial_without_overwrite(tmp_path):
    path = tmp_path/'failed.trajectory.jsonl'
    with CombatTrainingEnv(engine_factory=fixture) as env:
        _, info = env.reset(seed=0)
        with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat']) as writer:
            calls = []
            def cancel():
                calls.append(1)
                if len(calls) == 2:
                    raise RuntimeError('cancel sidecar publication')
            with pytest.raises(RuntimeError, match='cancel sidecar'):
                writer.finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop'),
                              combat_summary=info['combat'], terminated=False, truncated=True, check_cancel=cancel)
    assert path.exists() and not writer.path.exists() and writer.partial.exists()
    load_trajectory(path)
    with pytest.raises(ValueError, match='published training'):
        load_training_episode(path, writer.partial, split='train')
    with pytest.raises(FileNotFoundError):
        load_training_episode(path, writer.path, split='train')


@pytest.mark.parametrize('phase', ['canonical_cancel', 'sidecar_race'])
def test_cancellation_or_concurrent_sidecar_never_publishes_over_existing_data(tmp_path, phase):
    path = tmp_path/'publication.trajectory.jsonl'
    with CombatTrainingEnv(engine_factory=fixture) as env:
        _, info = env.reset(seed=0)
        with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat']) as writer:
            calls = []
            def during_publication():
                calls.append(1)
                if phase == 'canonical_cancel':
                    raise RuntimeError('cancel canonical publication')
                if len(calls) == 2:
                    writer.path.write_text('concurrent artifact')
            with pytest.raises(RuntimeError if phase == 'canonical_cancel' else FileExistsError):
                writer.finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop'),
                              combat_summary=info['combat'], terminated=False, truncated=True,
                              check_cancel=during_publication)
    assert writer.partial.exists()
    if phase == 'canonical_cancel':
        assert not path.exists() and not writer.path.exists() and writer.writer.partial.exists()
        assert writer.writer.completion is None
    else:
        assert path.exists() and writer.path.read_text() == 'concurrent artifact'
        assert writer.writer.completion is not None


def test_no_clobber_and_full_record_pair_is_public_only(pair, monkeypatch):
    texts = [p.read_text() for p in pair]
    for text in texts:
        for forbidden in ('"seed"', '"rng"', '"snapshot"', '"binding"', '"audit"', '"private"'):
            assert forbidden not in text
    trajectory = load_trajectory(pair[0])
    initial = json.loads(texts[1])['initial_combat']
    with pytest.raises(FileExistsError):
        CombatTrainingRecorder(pair[0], trajectory.metadata, trajectory.initial, initial)
    assert texts == [p.read_text() for p in pair]
    opened, original = [], Path.open
    def checked(path, *args, **kwargs):
        opened.append(path)
        assert path in pair
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', checked)
    load_training_episode(*pair, split='train')
    assert set(opened) == set(pair)


@pytest.mark.parametrize('card,expected_hp,expected_max', [('strike', 46, 80), ('hemokinesis', 44, 80), ('feed', 49, 83)])
def test_post_hook_hp_cost_healing_and_max_hp_are_measured_at_victory(card, expected_hp, expected_max):
    with CombatTrainingEnv(engine_factory=lambda seed: fixture(seed, cards=(card,)),
                           reward_spec=RewardSpec({'win_hp_fraction': 0.25})) as env:
        _, info = env.reset(seed=0)
        assert info['training_reward'] is None
        _, reward, done, cut, info = act(env, 'play_card')
        assert done and not cut
        assert (info['combat']['hp'], info['combat']['max_hp']) == (expected_hp, expected_max)
        assert reward == 1 + 0.25*expected_hp/expected_max
        assert info['training_reward']['components']['win_hp_fraction'] == expected_hp/expected_max
        with pytest.raises(gym.error.ResetNeeded):
            env.step(0)
        assert env.reset(seed=0)[1]['training_reward'] is None


@pytest.mark.parametrize('potion', ['blood_potion', 'entropic_brew', 'gamblers_brew'])
def test_potion_action_is_counted_once_despite_healing_replacement_or_selector_toggles(potion):
    run = fixture(3, cards=('strike', 'defend', 'bash'), enemy_hp=100, potions=(potion,))
    with CombatTrainingEnv(engine_factory=lambda seed: run,
                           reward_spec=RewardSpec({'potion_use_action': -0.02, 'end_turn_action': -0.01})) as env:
        env.reset(seed=0)
        _, reward, done, cut, info = act(env, 'use_potion')
        assert (reward, done, cut) == (-0.02, False, False)
        assert info['training_reward']['components']['potion_use_action'] == 1
        if potion == 'blood_potion':
            assert info['combat']['hp'] == 56
        elif potion == 'entropic_brew':
            assert sum(p is not None for p in run.state.potions) > 1
        else:
            for command in ('select_card', 'deselect_card', 'confirm_selection'):
                _, reward, done, cut, info = act(env, command)
                assert reward == 0 and not done and not cut
                assert all(v == 0 for v in info['training_reward']['components'].values())
        before = run.snapshot()
        assert env.step(-1)[1] == 0 and env._info()['training_reward'] is None
        assert run.snapshot() == before
        _, reward, done, cut, info = act(env, 'end_turn')
        assert reward == -0.01 and not done and not cut
        assert info['training_reward']['components']['end_turn_action'] == 1


def test_changing_objective_preserves_game_rng_and_public_trajectory():
    with CombatTrainingEnv(max_decisions=5) as default, CombatTrainingEnv(
            max_decisions=5, reward_spec=RewardSpec({'combat_loss': -1, 'end_turn_action': -0.1})) as shaped:
        default.reset(seed=42)
        shaped.reset(seed=42)
        for _ in range(5):
            assert default.public_state == shaped.public_state
            assert default._adapter._engine.snapshot() == shaped._adapter._engine.snapshot()
            a, b = default.step(0), shaped.step(0)
            assert a[2:4] == b[2:4]
            assert a[4]['combat'] == b[4]['combat'] and a[4]['outcome'] == b[4]['outcome']
            if a[2] or a[3]:
                break
        assert default.public_state == shaped.public_state
        assert default._adapter._engine.snapshot() == shaped._adapter._engine.snapshot()
