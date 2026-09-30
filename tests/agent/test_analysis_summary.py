"""Quick results are metadata-only and retain failures and source identities."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game.agent.analysis.sources import digest
from game.agent.analysis.summary import quick_summary
from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.rewards import RewardSpec
from .test_analysis import panel, record


def _ppo(root, *, status='complete'):
    root.mkdir(parents=True)
    spec = RewardSpec.with_act_rewards({'act_cleared': 1}, goal='act1')
    experiment = PPOExperiment(TrainingConfig('full_run', RUN_SCENARIO_SET, spec),
        PPOConfig(), ('overgrowth', 'underdocks'), RUN_SCENARIO_SET)
    value = {'schema': 'sts_ppo_report_v1', 'status': status, 'experiment': experiment.to_dict(),
             'experiment_identity': experiment.identity, 'summary': {'trained_decisions': 50, 'failed_episodes': 1},
             'iterations': [{'rollout': 'rollout-00001.json', 'rollout_sha256': 'a'*64}],
             'start_decisions': 0, 'final_sha256': 'b'*64}
    (root/'ppo.json').write_text(json.dumps(value))
    return value


def test_summary_never_opens_trajectories_rollouts_private_or_untrusted_paths(tmp_path, monkeypatch):
    root = tmp_path/'input'
    original = _ppo(root)
    record(root)
    (root/'rollout-00001.json').write_text('MUST NOT OPEN')
    private = root/'check-private'; private.mkdir()
    (private/'ppo.json').write_text('MUST NOT OPEN')
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert path.name == 'ppo.json' and 'check-private' not in path.parts
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    result = quick_summary([root])
    assert result['status'] == 'summary_ready'
    assert result['validation']['scope'] == 'report_metadata_only'
    assert not result['validation']['canonical_trajectories_checked']
    assert not result['validation']['ppo_rollouts_checked']
    job = result['training'][0]
    assert job['reported_summary'] == original['summary']
    assert job['experiment_identity'] == original['experiment_identity']


def test_failed_training_jobs_remain_separate_and_stdlib_cli_works(tmp_path):
    root = tmp_path/'input'
    _ppo(root/'one', status='failed'); _ppo(root/'two')
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_analyze', 'summary', '--input', str(root)],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    jobs = json.loads(result.stdout)['training']
    assert [job['status'] for job in jobs] == ['failed', 'complete']
    assert [job['label'] for job in jobs] == ['one', 'two']


def test_evaluation_keeps_failure_denominators_and_checks_plan_without_recordings(tmp_path):
    path = record(tmp_path/'input')
    source, report = panel(path.parent, [path])
    path.unlink()
    plan_path = source.with_name('baseline-plan.json')
    plan = json.loads(plan_path.read_text())
    for n, status in enumerate(('failed', 'interrupted', 'unattempted'), 2):
        row = deepcopy(report['episodes'][0]); row.update(episode_id=str(n)*32, status=status)
        report['episodes'].append(row); plan['episodes'].append(row)
    plan_path.write_text(json.dumps(plan)); report['plan_sha256'] = digest(plan_path)
    source.write_text(json.dumps(report))
    result = quick_summary([source.parent])
    row = result['evaluation'][0]
    assert row['planned_episodes'] == 4
    assert row['episode_statuses'] == dict(truncated=1, failed=1, interrupted=1, unattempted=1)
    assert not result['validation']['paired_starts_checked']
    plan_path.write_text('{}')
    with pytest.raises(ValueError, match='changed evaluation plan'):
        quick_summary([source.parent])


def test_summary_rejects_changed_experiment_and_empty_input(tmp_path):
    root = tmp_path/'input'
    original = _ppo(root)
    original['experiment_identity'] = 'changed'
    (root/'ppo.json').write_text(json.dumps(original))
    with pytest.raises(ValueError, match='identity mismatch'):
        quick_summary([root])
    with pytest.raises(ValueError, match='No supported'):
        quick_summary([record(tmp_path/'bare')])
