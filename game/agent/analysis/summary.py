"""Quick reported results, explicitly separate from canonical replay validation."""
from collections import Counter
import time

from game.agent.training.ppo_config import PPOExperiment
from .sources import PANEL_SCHEMAS, REPORT_NAMES, collect_metadata, digest, discover, read_json


def quick_summary(inputs):
    """Read report metrics and evaluation plans, never rollouts or trajectories.

    Keep each source separate: consecutive PPO chunks and different learners
    cannot be inferred from directory names or safely pooled automatically.
    """
    started = time.perf_counter()
    paths = discover(inputs)
    reports = [(p, read_json(p)) for p in paths if p.name in REPORT_NAMES]
    panel_paths = {p for p, r in reports if r.get('schema') in PANEL_SCHEMAS}
    # Reuse the full export's plan checks without opening any PPO sidecars.
    collect_metadata([p for p in paths if p in panel_paths or p.name.endswith('-plan.json')])
    training, evaluation, unsupported = [], [], []
    for path, report in reports:
        schema = report.get('schema')
        source = {'name': path.name, 'directory': str(path.parent), 'sha256': digest(path)}
        common = {'source': source, 'status': report.get('status', 'not_recorded'),
                  'implementation': report.get('implementation'), 'runtime': report.get('runtime'),
                  'reported_summary': report.get('summary'), 'total_seconds': report.get('total_seconds')}
        if common['reported_summary'] is not None and type(common['reported_summary']) is not dict:
            raise ValueError('Expected a reported summary object')
        if schema == 'sts_ppo_report_v1':
            experiment = PPOExperiment.from_dict(report['experiment'])
            if experiment.identity != report['experiment_identity']:
                raise ValueError('PPO experiment identity mismatch')
            training.append({**common, 'label': path.parent.name, 'split': 'train',
                'experiment': experiment.to_dict(), 'experiment_identity': experiment.identity,
                'reported_episode_evidence_counts': dict(Counter(
                    episode.get('evidence', 'not_recorded') for iteration in report['iterations']
                    for episode in iteration.get('collection', {}).get('episodes', []))),
                **{key: report.get(key) for key in ('collection', 'initialization', 'limits',
                    'start_decisions', 'start_iteration', 'initial_sha256', 'final_sha256',
                    'last_complete_checkpoint', 'stop_reason', 'failure')}})
        elif schema in PANEL_SCHEMAS:
            evaluation.append({**common, 'schema': schema,
                'episode_statuses': dict(Counter(row['status'] for row in report['episodes'])),
                'planned_episodes': len(report['episodes']),
                **{key: report.get(key) for key in ('goal', 'split', 'evidence', 'policies',
                    'reward_spec', 'training_reward_spec', 'primary_metric', 'plan_sha256',
                    'paired_vs_heuristic', 'paired_vs_reference')}})
        else:
            unsupported.append({'source': source, 'schema': schema})
    if not training and not evaluation:
        raise ValueError('No supported PPO or evaluation reports found; include their public directories')
    return {'schema': 'sts_analysis_summary_v1', 'status': 'summary_ready',
            'validation': {'scope': 'report_metadata_only', 'evaluation_plan_bindings_checked': True,
                           'canonical_trajectories_checked': False, 'ppo_rollouts_checked': False,
                           'paired_starts_checked': False, 'checkpoint_files_checked': False},
            'limitations': [
                'Metrics and outcomes are reported by the experiment, not independently replay-validated.',
                'Evaluation denominators retain failed, interrupted and unattempted episodes.',
                'Sources remain separate; training outcomes are not final-policy evaluation.'],
            'training': training, 'evaluation': evaluation, 'unsupported_reports': unsupported,
            'seconds': time.perf_counter()-started}
