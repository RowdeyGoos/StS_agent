"""Critic diagnostics retain the public prefix, objective and outcome provenance."""
import gzip
import hashlib
import json
from pathlib import Path
import time
from dataclasses import replace

import pytest

from .test_search_training import checkpoint, cpu_threads
from .test_belief import actual, setup
from game.agent.input_views import planning_view
from game.agent.search import SearchConfig
from game.agent.search.public_keys import action_key
from game.agent.training.checkpoint import load_policy
from game.agent.training.search_run import audit_critic, run_search, reanalyse_search, _audit_rollout
from game.agent.training.scenarios import Scenario
from game.agent.recording import load_trajectory


def completed(checkpoint, tmp_path, monkeypatch, model='direct_belief_v1', *, split='validation'):
    declared = setup(deck=('defend',), hp=20, relics=(('burning_blood', 0),))
    monkeypatch.setattr(Scenario, 'planning_start', lambda self: declared)
    monkeypatch.setattr(Scenario, 'make', lambda self, seed: actual(declared, seed=seed)[0])
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'source',
        search=SearchConfig(model_version=model, simulations=4, time_limit=20,
                            belief_particles=2, exploration=True),
        cases=1, split=split, collect=split == 'train', max_decisions=20)
    assert all(r['status'] == 'terminated' for r in report['episodes'])
    return path, report


@pytest.mark.parametrize('model', ['direct_belief_v1', 'public_belief_v1'])
def test_belief_audit_follows_original_actions_and_samples_only_public_worlds(checkpoint, tmp_path, monkeypatch, model):
    path, source = completed(checkpoint, tmp_path, monkeypatch, model)
    original = {p: p.read_bytes() for p in path.parent.iterdir() if p.is_file()}
    row = next(r for r in source['episodes'] if r['policy'] == 'gumbel')
    trajectory = load_trajectory(path.parent / row['trajectory'], split='validation')
    teacher = load_policy(checkpoint)

    def forbidden(*args, **kwargs):
        raise AssertionError('Audit tried a private start or the wrong simulation model')
    monkeypatch.setattr(Scenario, 'make', forbidden)
    monkeypatch.setattr('game.agent.search.model.PublicCombatModel', forbidden)
    # Missing owner-only replay directories cannot affect this public-only audit.
    read_bytes, read_text = Path.read_bytes, Path.read_text
    monkeypatch.setattr(Path, 'read_bytes', lambda p: forbidden() if '-private' in str(p) else read_bytes(p))
    monkeypatch.setattr(Path, 'read_text', lambda p, *a, **k: forbidden() if '-private' in str(p) else read_text(p, *a, **k))
    reports = []
    for name in ('a', 'b'):
        _, report = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / (name + '.json'),
                                positions=2, rollouts=2, depth=32)
        reports.append(report)
    assert reports[0]['schema'] == 'sts_search_critic_audit_v2'
    assert reports[0]['selected_behavior'] == 'gumbel'
    assert reports[0]['search']['model_version'] == model
    assert not reports[0]['search']['exploration']
    assert reports[0]['summary']['positions'] == 2
    for item, again in zip(reports[0]['positions'], reports[1]['positions']):
        observation = trajectory.transitions[item['step']].observation
        if model == 'direct_belief_v1':
            observation = planning_view(observation)
        assert item['critic'] == teacher.probabilities(observation)[1]
        assert item['completed_behavior_return'] == row['task_return'] == 0
        assert item['behavior_policy'] == source['policies']['gumbel']
        assert item['rollouts'] == again['rollouts']
        assert item['rollout_cutoffs'] == 0 and item['completed_rollout_returns'] == [0., 0.]
        assert all(r[arm]['status'] == 'completed' for r in item['rollouts'] for arm in ('greedy', 'search'))
        if not item['search_disagrees']:
            assert all(r['greedy'] == r['search'] for r in item['rollouts'])
    assert all(p.read_bytes() == data for p, data in original.items())


@pytest.mark.parametrize('change', ['anchor', 'targets_hash', 'view', 'target_model', 'completion', 'behavior', 'objective', 'held_out'])
def test_audit_rejects_missing_or_mixed_provenance_before_publishing(checkpoint, tmp_path, monkeypatch, change):
    path, report = completed(checkpoint, tmp_path, monkeypatch)
    row = next(r for r in report['episodes'] if r['policy'] == 'gumbel')
    target = path.parent / row['targets']
    data = json.loads(gzip.decompress(target.read_bytes()))
    if change == 'anchor':
        del data['planning']
    elif change == 'view':
        data['planning_view'] = 'public_observation_v1'
    elif change == 'target_model':
        data['search']['model_version'] = 'reconstruction_v1'
    elif change == 'completion':
        next(iter(data['planning']['completions'].values()))['run']['fields'] = []
    elif change == 'behavior':
        row['behavior_policy'] = 'not-the-recorded-policy'
    elif change == 'objective':
        report['reward_spec']['weights']['combat_win'] = 0.
    elif change == 'held_out':
        report['split'] = 'test'
    target.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    if change != 'targets_hash':
        row['targets_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_text(json.dumps(report))
    output = tmp_path / 'rejected.json'
    with pytest.raises(ValueError):
        audit_critic(checkpoint=checkpoint, report_path=path, output_path=output, positions=1, rollouts=1)
    assert not output.exists()


def test_rollout_cutoffs_have_no_fabricated_value(checkpoint):
    declared = setup(deck=('strike', 'defend'), relics=(('burning_blood', 0),))
    run, adapter = actual(declared)
    decision = adapter.observe().decision
    teacher = load_policy(checkpoint)
    key = action_key(decision, teacher(decision))
    from game.agent.search.direct import DirectCombatBelief
    model = DirectCombatBelief(declared, decision, seed=0)
    real_before = run.snapshot()
    root_before = model.current
    timed = _audit_rollout(model, 7, key, teacher, 64, time.perf_counter()-1, None)
    shallow = _audit_rollout(model, 7, key, teacher, 1, time.perf_counter()+30, None)
    assert timed == dict(status='cutoff', reason='rollout_time_budget', steps=0)
    assert shallow == dict(status='cutoff', reason='rollout_depth_budget', steps=1)
    assert run.snapshot() == real_before and model.current == root_before
    assert 'value' not in timed and 'value' not in shallow


def test_audit_cancellation_and_invalid_limits(checkpoint, tmp_path, monkeypatch):
    from threading import Event
    path, source = completed(checkpoint, tmp_path, monkeypatch)
    cancelled = Event()
    cancelled.set()
    _, audit = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / 'cancelled.json', cancel=cancelled)
    assert audit['status'] == 'interrupted' and not audit['positions']
    for seconds in (0., -1., float('nan'), float('inf'), 601., True):
        with pytest.raises(ValueError, match='deadline'):
            audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / 'invalid.json', rollout_seconds=seconds)


def test_audit_continues_recorded_prefix_after_a_different_recommendation(checkpoint, tmp_path, monkeypatch):
    from game.agent.search import SearchPolicy
    path, source = completed(checkpoint, tmp_path, monkeypatch)
    row = next(r for r in source['episodes'] if r['policy'] == 'gumbel')
    trajectory = load_trajectory(path.parent / row['trajectory'], split='validation')
    choose = SearchPolicy.choose
    visited = []
    def disagree(self, observation):
        visited.append(observation)
        result = choose(self, observation)
        if len(visited) == 1:
            alternate = next(a for a in observation.candidates if a.ref != trajectory.transitions[0].action.ref)
            result = replace(result, action_ref=alternate.ref)
        return result
    monkeypatch.setattr(SearchPolicy, 'choose', disagree)
    _, audit = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / 'audit.json',
                            positions=2, rollouts=2, depth=32)
    assert audit['positions'][0]['search_action_ref'] != trajectory.transitions[0].action.ref
    assert len(visited) == 2 and visited[1] == trajectory.transitions[len(trajectory.transitions)//2].observation
    assert all(item['search_fallback'] is None for item in audit['positions'])
    assert all(not item.get('rollout_fallback') for item in audit['positions'])


def test_refreshed_audit_retains_original_behavior_build(checkpoint, tmp_path, monkeypatch):
    import game.agent.training.search_run as owner
    from game.agent.provenance import implementation
    path, source = completed(checkpoint, tmp_path, monkeypatch, split='train')
    old_build = source['implementation']['build']
    # Reanalysis under another implementation preserves original trajectory
    # bytes. It must not pretend the newer teacher created that behavior.
    monkeypatch.setattr(owner, 'implementation', lambda: replace(implementation(), build='f'*64))
    refreshed, report = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'refreshed', search=SearchConfig(**source['search_configs']['gumbel']))
    assert report['implementation']['build'] != old_build
    _, audit = audit_critic(checkpoint=checkpoint, report_path=refreshed, output_path=tmp_path / 'audit.json',
                            positions=1, rollouts=1, depth=32)
    assert audit['source_bindings'][0]['behavior_build'] == old_build
    assert audit['implementation']['build'] == report['implementation']['build']
    assert audit['positions'][0]['behavior_policy'] == source['policies']['gumbel']
