"""Search inspection binds public evidence without running search or reading worlds."""
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from game.agent import contracts as c
from game.agent.action_policy import ALL_LEGAL
from game.agent.analysis.decisions import state_digest
from game.agent.analysis.report import build_report
from game.agent.analysis.search import collect_search, validate_search, OBJECTIVE
from game.agent.analysis.server import AnalysisStore
from game.agent.analysis.sources import digest, discover
from game.agent.contracts import full as f
from game.agent.input_views import RAW, DETACHED_HISTORY, apply_view
from game.agent.recording import load_trajectory
from game.agent.search import SearchConfig, SearchPolicy
from .test_analysis import public, record


def fixture(root, *, report=False, purpose='evaluation', legacy=False, search_settings=None, model=None):
    state = public(candidates=tuple(f.Candidate(f'action:{i}', 'play_card', f'card:{i}') for i in range(4)))
    # A card-history link actually changes under the planning view. This catches
    # accidentally recomputing direct search priors from the raw observation.
    history = f.Node('history', 'history', children=(f.Node('action', 'play_card', links=(
        f.Link('history_subject', ('card:0',)),)),))
    cards = tuple(replace(state.run.children[0], ref=f'card:{i}') for i in range(4))
    state = replace(state, run=replace(state.run, children=(*cards, history)))
    config = SearchConfig(simulations=4, considered_actions=4, max_depth=8,
                          model_version=model or ('reconstruction_v1' if legacy else 'direct_belief_v1'),
                          **(search_settings or {}))
    checkpoint = 'imitation_v1:' + 'c'*64
    base = SimpleNamespace(identity=checkpoint, reward_spec=OBJECTIVE,
                           model=SimpleNamespace(input_view=RAW, action_policy=ALL_LEGAL))
    teacher = SearchPolicy(base, config).identity
    path = record(root, start=state, policy='original-behavior' if purpose == 'reanalysis' else teacher)
    trace = load_trajectory(path)
    refs = [a.ref for a in state.candidates]
    target = {'step': 0, 'action_ref': refs[1] if purpose == 'reanalysis' else refs[0],
              'probabilities': dict(zip(refs, [.55, .25, .1, .1])),
              'values': dict(zip(refs, [1.05, 1.1, .3, .6])),
              'visits': dict(zip(refs, [2, 1, 1, 0])), 'simulations': 4,
              'seconds': .3, 'reason': None, 'cutoff': None,
              'timings': {'inference': .15, 'transition': .1}, 'leaf_work': {},
              'tree_work': {'depth_histogram': {'1': 4}, 'expansions': 3, 'terminals': 1,
                            'root_rounds': [
                                {'ranked': refs, 'visits': dict(zip(refs, [1, 1, 1, 0])),
                                 'simulations_before': 0, 'simulations_after': 3},
                                {'ranked': refs[:2], 'visits': dict(zip(refs[:2], [2, 1])),
                                 'simulations_before': 3, 'simulations_after': 4}]}}
    data = {'schema': 'sts_search_targets_v1' if legacy else 'sts_search_targets_v2',
            'trajectory_sha256': trace.sha256, 'checkpoint': checkpoint, 'teacher': teacher,
            'split': 'validation', 'reward_spec': OBJECTIVE.to_dict(), 'search': asdict(config),
            'targets': [target], 'planning_view': RAW if legacy else DETACHED_HISTORY,
            'planning': {'must_not_be_exported': 'OMIT-PLANNING-SUPPLEMENT'}}
    if legacy:
        del data['planning_view']
        del target['tree_work']
        del target['leaf_work']
        del target['cutoff']
    sidecar = root/(trace.metadata.episode_id + '.search.json.gz')
    sidecar.write_bytes(gzip.compress(json.dumps(data).encode()))
    if report:
        row = {'episode_id': trace.metadata.episode_id, 'steps': 1, 'policy': 'gumbel',
               'behavior_policy': trace.metadata.policy, 'run_outcome': c.to_dict(trace.outcome),
               'trajectory': path.name, 'targets': sidecar.name, 'targets_sha256': digest(sidecar)}
        source = {'schema': 'sts_search_report_v1' if legacy else 'sts_search_report_v2',
                  'purpose': purpose, 'episodes': [row], 'split': 'validation', 'checkpoint': checkpoint,
                  'reward_spec': OBJECTIVE.to_dict(), 'policies': {'gumbel': teacher},
                  'search_configs': {'gumbel': asdict(config)}}
        if not legacy:
            source['planning_view'] = DETACHED_HISTORY
        (root/'search.json').write_text(json.dumps(source))
    return path, sidecar, data


def loaded(path):
    bindings, _, _ = collect_search(discover([path.parent]))
    return validate_search(load_trajectory(path), bindings[path])


def test_observed_model_exports_diagnostics_without_its_planning_receipts(tmp_path):
    path, _, _ = fixture(tmp_path/'input', report=True, model='revealed_belief_v1')
    meta, decisions = loaded(path)
    assert decisions and 'OMIT-PLANNING-SUPPLEMENT' not in json.dumps([meta, decisions])


@pytest.mark.parametrize('settings', [{}, {'q_scale': 1.}, {'final_selection': 'max_value'}])
def test_selection_diagnostics_keep_versioned_teacher_and_public_evidence(tmp_path, settings):
    path, sidecar, data = fixture(tmp_path/'input', search_settings=settings)
    target = data['targets'][0]
    tree = target['tree_work']
    tree['root_value'] = .5
    tree['root_evidence'] = {ref: dict(prior=.25, tree_terminals=int(ref == 'action:0'),
        leaf_terminals=0, critic_bootstraps=n-int(ref == 'action:0'),
        value_sum_squares=n * target['values'][ref] ** 2) for ref, n in target['visits'].items()}
    for row in tree['root_rounds']:
        row['values'] = {ref: target['values'][ref] for ref in row['ranked']}
        row['scores'] = {ref: float(i) for i, ref in enumerate(row['ranked'])}
    sidecar.write_bytes(gzip.compress(json.dumps(data).encode()))
    _, decisions = loaded(path)
    assert decisions[0]['tree_work'] == tree
    for mutate in (
        lambda t: t['root_evidence']['action:0'].update(critic_bootstraps=2),
        lambda t: t['root_evidence']['action:0'].update(value_sum_squares=float('nan')),
        lambda t: t['root_rounds'][0]['scores'].update(**{'private:999': 1.}),
    ):
        broken = deepcopy(data)
        mutate(broken['targets'][0]['tree_work'])
        sidecar.write_bytes(gzip.compress(json.dumps(broken).encode()))
        with pytest.raises(ValueError):
            loaded(path)


@pytest.mark.parametrize('workers', [1, 2])
@pytest.mark.parametrize('with_report', [False, True])
def test_search_export_retains_only_bound_public_diagnostics(tmp_path, workers, with_report):
    path, sidecar, data = fixture(tmp_path/'input', report=with_report)
    private = path.parent/'audit'; private.mkdir(); (private/'search.json').write_text('SECRET')
    report = build_report([path.parent], tmp_path/'report', workers=workers)
    store = AnalysisStore(tmp_path/'report')
    row = report['runs'][0]; value = store.decision(row['id'], 0)
    assert value['search']['visits'] == data['targets'][0]['visits']
    assert value['search']['probabilities'] == data['targets'][0]['probabilities']
    assert row['search']['source']['sha256'] == digest(sidecar)
    assert row['search']['searched'] == 1 and row['training'] is None
    assert 'OMIT-PLANNING' not in json.dumps(value) + json.dumps(report)
    assert 'SECRET' not in json.dumps(report)
    # The canonical cutoff remains a cutoff, never relabelled a combat defeat.
    assert row['status'] == 'cutoff' and row['outcome']['kind'] == 'truncated'
    assert store.compare(row['id'], 0)['search_actor']['status'] == 'checkpoint_not_loaded'
    path.unlink(); sidecar.unlink()
    assert store.decision(row['id'], 0) == value  # The export is self-contained.


@pytest.mark.parametrize('edit', [
    lambda d: d.update(trajectory_sha256='0'*64),
    lambda d: d.update(teacher='different'),
    lambda d: d.update(checkpoint='different'),
    lambda d: d.update(split='test'),
    lambda d: d.update(planning_view=RAW),
    lambda d: d.pop('planning_view'),
    lambda d: d['reward_spec']['weights'].update(combat_win=0.),
    lambda d: d['targets'][0].update(step=True),
    lambda d: d['targets'][0].update(step=1),
    lambda d: d['targets'][0].update(action_ref='action:1'),
    lambda d: d['targets'][0]['probabilities'].update(**{'action:999': .2}),
    lambda d: d['targets'][0]['probabilities'].update(**{'action:0': .7}),
    lambda d: d['targets'][0]['probabilities'].update(**{'action:0': True}),
    lambda d: d['targets'][0]['values'].update(**{'action:0': float('nan')}),
    lambda d: d['targets'][0]['visits'].update(**{'action:0': 3}),
    lambda d: d['targets'][0].update(seconds=-1),
    lambda d: d['targets'][0]['tree_work']['root_rounds'][0]['ranked'].append('action:0'),
    lambda d: d['targets'][0]['tree_work']['root_rounds'][1].update(
        ranked=['action:0', 'action:2'], visits={'action:0': 2, 'action:2': 1}),
])
def test_search_rejects_corrupt_join_and_statistics(tmp_path, edit):
    path, sidecar, data = fixture(tmp_path/'input')
    edit(data)
    sidecar.write_bytes(gzip.compress(json.dumps(data).encode()))
    with pytest.raises(ValueError):
        loaded(path)


def test_report_hash_behavior_and_explicit_discovery_are_required(tmp_path):
    path, sidecar, data = fixture(tmp_path/'input', report=True)
    source = path.parent/'search.json'
    report = json.loads(source.read_text())
    report['episodes'][0]['targets_sha256'] = '0'*64
    source.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='binding'):
        loaded(path)
    # A report is not permission to read sibling paths not explicitly discovered.
    with pytest.raises(ValueError, match='Missing public search artifact'):
        collect_search([source, path])
    for filename in ('../outside.search.json.gz', '/tmp/outside.search.json.gz'):
        report['episodes'][0]['targets'] = filename
        source.write_text(json.dumps(report))
        with pytest.raises(ValueError, match='sibling'):
            collect_search(discover([path.parent]))


def test_private_and_symlink_sidecars_are_not_followed(tmp_path):
    path, sidecar, _ = fixture(tmp_path/'input', report=True)
    moved = tmp_path/'input-private'/sidecar.name
    moved.parent.mkdir(); sidecar.rename(moved); sidecar.symlink_to(moved)
    with pytest.raises(ValueError, match='Missing public search artifact'):
        collect_search(discover([path.parent]))
    with pytest.raises(ValueError, match='public paths'):
        discover([sidecar])


def test_reanalysis_may_suggest_a_different_action_but_never_relabels_play(tmp_path):
    path, sidecar, data = fixture(tmp_path/'input', report=True, purpose='reanalysis')
    report = build_report([path.parent], tmp_path/'report')
    store = AnalysisStore(tmp_path/'report'); row = report['runs'][0]
    value = store.decision(row['id'], 0)
    assert row['search']['purpose'] == 'reanalysis'
    assert row['metadata']['policy'] == 'original-behavior'
    assert row['policy'].startswith('Original behavior') and row['search']['policy_label'] == 'gumbel'
    assert value['action']['ref'] == 'action:0' and value['search']['action_ref'] == 'action:1'
    (path.parent/'search.json').unlink()
    with pytest.raises(ValueError, match='reanalysis requires'):
        loaded(path)


def test_search_report_coverage_does_not_hide_failed_episodes(tmp_path):
    path, _, _ = fixture(tmp_path/'input', report=True)
    source = path.parent/'search.json'; report = json.loads(source.read_text())
    report['goal'] = 'act1'
    report['episodes'].append({'episode_id': '2'*32, 'policy': 'gumbel', 'status': 'failed'})
    source.write_text(json.dumps(report))
    exported = build_report([path.parent], tmp_path/'report')
    assert exported['pending'][0]['reported_status'] == 'failed'
    assert exported['pending'][0]['goal'] == 'act1'
    assert exported['sources'][0]['coverage'] == 'recorded_search_targets_only'


def test_old_search_and_unsearched_recordings_keep_missing_diagnostics_explicit(tmp_path):
    path, sidecar, _ = fixture(tmp_path/'input', legacy=True)
    meta, rows = loaded(path)
    assert meta['planning_view'] == RAW
    assert rows[0]['tree_work'] is None and rows[0]['leaf_work'] is None
    sidecar.unlink()
    report = build_report([path.parent], tmp_path/'report')
    assert report['runs'][0]['search'] is None
    assert AnalysisStore(tmp_path/'report').decision(report['runs'][0]['id'], 0)['search'] is None


@pytest.mark.parametrize('reason,simulations', [('belief_budget', 0), (None, 4), ('unsupported_transition', 4)])
def test_fallbacks_and_search_cutoffs_remain_separate_from_game_outcomes(tmp_path, reason, simulations):
    path, sidecar, data = fixture(tmp_path/'input')
    row = data['targets'][0]
    row.update(reason=reason, cutoff='search_time_budget', simulations=simulations)
    if simulations == 0:
        row.update(visits={ref: 0 for ref in row['visits']}, tree_work={})
    sidecar.write_bytes(gzip.compress(json.dumps(data).encode()))
    meta, values = loaded(path)
    assert values[0]['reason'] == reason and values[0]['cutoff'] == 'search_time_budget'
    assert meta['searched'] == (reason is None)


def test_matching_search_actor_uses_recorded_view_and_checks_support_and_objective(tmp_path):
    path, _, _ = fixture(tmp_path/'input')
    report = build_report([path.parent], tmp_path/'report')
    store = AnalysisStore(tmp_path/'report'); key = report['runs'][0]['id']
    value = store.decision(key, 0); raw = f.from_dict(value['observation'])
    observed = []
    def probabilities(decision):
        observed.append(decision)
        return {a.ref: .25 for a in decision.candidates}, 1.7
    policy = SimpleNamespace(identity=report['runs'][0]['search']['checkpoint'],
                             reward_spec=OBJECTIVE, probabilities=probabilities,
                             model=SimpleNamespace(input_view=RAW, action_policy=ALL_LEGAL))
    store.models = {'teacher': policy}
    store.model_info = [{'label': 'teacher', 'identity': policy.identity}]
    actor = store._search_actor(key, value, raw)
    assert actor['status'] == 'available' and actor['critic'] == 1.7 and actor['search_value'] == 1.1
    assert observed == [apply_view(raw, DETACHED_HISTORY)] and observed[0] != raw
    assert actor['input_state_sha256'] == state_digest(observed[0])
    assert raw == f.from_dict(value['observation'])  # No mutation of recorded state.
    changed = deepcopy(value); changed['search']['probabilities'].pop('action:3')
    assert store._search_actor(key, changed, raw)['status'] == 'incompatible'
    from game.agent.training.rewards import RewardSpec
    policy.reward_spec = RewardSpec()
    assert store._search_actor(key, value, raw)['status'] == 'incompatible'
    assert len(observed) == 1  # Fail mismatches before inference.


def test_search_export_does_not_require_training_or_engine_execution(tmp_path):
    path, _, _ = fixture(tmp_path/'input')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_analyze', 'build',
        '--input', str(path.parent), '--output-dir', str(tmp_path/'report'), '--workers', '1'],
        cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
