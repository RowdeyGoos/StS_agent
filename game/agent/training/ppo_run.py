"""Bounded PPO experiments with atomic journals and last-complete checkpoints."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import time

from game.agent.provenance import implementation
from game.agent.action_policy import ALL_LEGAL
from game.agent.runner import RunCancelled, prepare_directories
from game.agent.tracking import report_progress
from .checkpoint import load_policy, publish, restore_ppo, runtime, save_ppo_checkpoint
from .ppo import PPOLearner, UPDATE_POLICY
from .rollout import advantages, check_cancel
from .rewards import ACT_RUN_SCHEMA, DEFEAT_HP_SCHEMA, POTENTIAL_SCHEMA, SHAPED_RUN_SCHEMAS


def _publish_json(path, value):
    return publish(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())


def _rollout_record(rollout, experiment):
    adv, returns = advantages(rollout.steps, gamma=experiment.ppo.gamma, gae_lambda=experiment.ppo.gae_lambda)
    shaped = experiment.training.reward.schema in SHAPED_RUN_SCHEMAS
    potential = experiment.training.reward.schema == POTENTIAL_SCHEMA
    defeat_hp = experiment.training.reward.schema == DEFEAT_HP_SCHEMA
    restricted = experiment.training.action_policy != ALL_LEGAL
    return {'schema':'sts_ppo_rollout_v6' if defeat_hp else 'sts_ppo_rollout_v5' if potential else
                    'sts_ppo_rollout_v4' if experiment.training.reward.schema == ACT_RUN_SCHEMA else
                    'sts_ppo_rollout_v3' if restricted else 'sts_ppo_rollout_v2' if shaped else 'sts_ppo_rollout_v1',
            **({'reward_spec':experiment.training.reward.to_dict()} if shaped or potential or defeat_hp else {}),
            **({'action_policy':experiment.training.action_policy} if restricted else {}),
            'behavior':rollout.behavior, 'iteration':rollout.iteration,
            'experiment':experiment.identity, 'episodes':rollout.progress['episodes'],
            'steps':[{'episode_id':s.episode_id, 'episode_step':s.episode_step,
                'candidate_refs':list(s.candidate_refs),
                'legal_mask':list(s.state.legal_mask),
                **({'policy_mask':list(s.mask)} if restricted else {}),
                'action':s.action, 'action_ref':s.candidate_refs[s.action],
                'old_log_probability':s.old_log_probability, 'value':s.value, 'next_value':s.next_value,
                'reward':s.reward, 'components':s.components, 'terminated':s.terminated, 'truncated':s.truncated,
                'advantage':a, 'return':r,
                **({'reward_context':s.reward_context} if shaped else {})}
                for s,a,r in zip(rollout.steps, adv.tolist(), returns.tolist())]}


def _peak_rss():
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == 'darwin' else value*1024


def run_ppo(*, checkpoint, experiment, output_dir, decisions=256, time_limit_seconds=3600,
            resume_state=None, seed=None, start_index=None, cancel=None, env_factory=None, audit_dir=None,
            workers=None, reset_objective=False, reset_action_policy=False, reset_representation=False):
    if type(decisions) is not int or not 1 <= decisions <= 20000:
        raise ValueError('Choose 1–20,000 bounded PPO decisions per invocation')
    if (type(time_limit_seconds) not in (int, float) or not math.isfinite(time_limit_seconds) or
            not 0 < time_limit_seconds <= 3600):
        raise ValueError('Choose a positive PPO time budget of at most one hour')
    if resume_state is not None and (seed is not None or start_index is not None):
        raise ValueError('Exact PPO resume restores RNG and episode cursor; omit --seed/--start-index')
    if type(reset_objective) is not bool or reset_objective and resume_state is not None:
        raise ValueError('Objective reset starts a new experiment; it cannot resume optimizer state')
    if type(reset_action_policy) is not bool or reset_action_policy and resume_state is not None:
        raise ValueError('Action-policy reset starts a new experiment; it cannot resume optimizer state')
    if type(reset_representation) is not bool or reset_representation and (
            resume_state is not None or reset_objective or reset_action_policy):
        raise ValueError('Representation reset starts a separate experiment; do not combine with resume or other resets')
    policy = load_policy(checkpoint, reward_spec=None if reset_objective else experiment.training.reward)
    changed_actions = policy.model.action_policy != experiment.training.action_policy
    if changed_actions != reset_action_policy:
        raise ValueError('A different action policy requires --reset-action-policy; omit it for an unchanged policy')
    model, transfer = policy.model, None
    representation_transfer = None
    if reset_representation:
        from .run_corpus import transfer_catalog
        model, representation_transfer = transfer_catalog(policy, seed=0 if seed is None else seed)
    if reset_objective:
        from .run_corpus import transfer_run_objective
        model, transfer = transfer_run_objective(policy, experiment.training.reward,
                                                 seed=0 if seed is None else seed)
    if reset_action_policy:
        from .model import ActorCritic
        initialized = ActorCritic(model.vocabulary, model.architecture,
                                 action_policy=experiment.training.action_policy, input_view=model.input_view)
        initialized.load_state_dict(model.state_dict(), strict=True)
        model = initialized
    learner = (restore_ppo(checkpoint, resume_state, experiment=experiment, env_factory=env_factory, workers=workers)
               if resume_state is not None else PPOLearner(model, experiment,
                    seed=0 if seed is None else seed, cursor=0 if start_index is None else start_index,
                    env_factory=env_factory, workers=1 if workers is None else workers))
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, audit_dir or output.with_name(output.name+'-private'))
    report_path = output/'ppo.json'
    if report_path.exists() or report_path.with_name(report_path.name+'.partial').exists() or (output/'initial.sts-model').exists():
        raise FileExistsError(output)
    started, deadline = time.perf_counter(), time.monotonic()+time_limit_seconds
    report = {'schema':'sts_ppo_report_v1', 'status':'running', 'implementation':asdict(implementation()),
        'runtime':runtime(), 'experiment':experiment.to_dict(), 'experiment_identity':experiment.identity,
        'collection':learner.collection_settings, 'update_policy':UPDATE_POLICY,
        'initialization':{'checkpoint':policy.identity, 'resumed':resume_state is not None},
        'limits':{'additional_decisions':decisions, 'wall_seconds':time_limit_seconds},
        'start_decisions':learner.decisions, 'start_iteration':learner.iterations, 'iterations':[]}
    if transfer is not None:
        report['initialization']['objective_transfer'] = transfer
    if representation_transfer is not None:
        report['initialization']['representation_transfer'] = representation_transfer
    if reset_action_policy:
        report['initialization']['action_policy_transfer'] = {
            'source':policy.model.action_policy, 'target':model.action_policy,
            'actor_weights_retained':True, 'critic_weights_retained':not reset_objective,
            'fresh_optimizer_rng_and_cursor':True}
    report['initial_sha256'] = save_ppo_checkpoint(output/'initial.sts-model', learner,
                                                  resume_path=private/'initial.resume.pt')
    report['last_complete_checkpoint'] = 'initial.sts-model'
    report_progress(report_path, report)
    consumed = 0
    entry = None
    try:
        while consumed < decisions:
            check_cancel(cancel)
            if time.monotonic() >= deadline:
                report.update(status='budget_reached', stop_reason='time_budget')
                break
            entry = {'iteration':learner.iterations+1}
            report['iterations'].append(entry)
            rollout = learner.collect(decisions=min(experiment.ppo.rollout_steps, decisions-consumed),
                output_dir=output, audit_dir=private, cancel=cancel, deadline=deadline)
            entry['collection'] = rollout.progress
            consumed += len(rollout.steps)
            if not rollout.steps:
                report.update(status='budget_reached', stop_reason=rollout.progress['stop_reason'] or 'no_progress')
                break
            filename = f'rollout-{entry["iteration"]:05}.json'
            entry['rollout'] = filename
            entry['rollout_sha256'] = _publish_json(output/filename, _rollout_record(rollout, experiment))
            entry['update'] = learner.update(rollout, cancel=cancel, deadline=deadline)
            filename = f'update-{learner.iterations:05}.sts-model'
            entry['checkpoint_sha256'] = save_ppo_checkpoint(output/filename, learner,
                resume_path=private/f'update-{learner.iterations:05}.resume.pt')
            report['last_complete_checkpoint'] = filename
            report_progress(report_path, report)
            if rollout.progress['stop_reason'] is not None:
                report.update(status='budget_reached', stop_reason=rollout.progress['stop_reason'])
                break
        else:
            report['status'] = 'complete'
        if learner.phase == 'boundary':
            report['final_sha256'] = save_ppo_checkpoint(output/'final.sts-model', learner,
                                                         resume_path=private/'final.resume.pt')
            report['last_complete_checkpoint'] = 'final.sts-model'
    except (RunCancelled, KeyboardInterrupt):
        report.update(status='cancelled', stop_reason='cancellation')
    except TimeoutError:
        report.update(status='budget_reached', stop_reason='time_budget', discarded_partial_update=True)
    except Exception as error:
        report.update(status='failed', failure=getattr(error, 'reason', type(error).__name__))
    finally:
        try:
            learner.close()
        except Exception as error:
            report.update(status='failed', failure=type(error).__name__, cleanup_failed=True)
        if entry is not None and 'collection' not in entry:
            entry['collection'] = learner.latest_collection
        report['total_seconds'] = time.perf_counter()-started
        report['peak_process_rss_bytes'] = _peak_rss()
        report['peak_process_rss_scope'] = 'parent_process_only'
    collections = [i['collection'] for i in report['iterations'] if 'collection' in i]
    episodes = [e for batch in collections for e in batch.get('episodes', [])]
    full_run = experiment.training.mode == 'full_run'
    def outcome(e):
        return (e.get('outcome') or {}).get('kind') if full_run else (e.get('combat') or {}).get('outcome')
    wins = [e for e in episodes if outcome(e) == 'victory']
    report['summary'] = {'episode_attempts':len(episodes), 'wins':len(wins),
        'losses':sum(outcome(e) == 'defeat' for e in episodes),
        'cutoffs':sum(e['status']=='truncated' for e in episodes),
        'failed_episodes':sum(e['status']=='failed' for e in episodes),
        'accepted_decisions':sum(b.get('steps', 0) for b in collections),
        'processed_decisions':learner.decisions-report['start_decisions'],
        'trained_decisions':sum(i['update']['decisions'] for i in report['iterations']
                                if i.get('update', {}).get('status') == 'updated'),
        'skipped_decisions':sum(i['update']['decisions'] for i in report['iterations']
                                if i.get('update', {}).get('status') == 'skipped'),
        'skipped_updates':sum(i.get('update', {}).get('status') == 'skipped' for i in report['iterations']),
        'mean_hp_on_win':sum(e['end_hp'] for e in wins)/len(wins) if wins and not full_run else None,
        'potion_use_actions':sum(e['potion_use_actions'] for e in episodes),
        'task_return':sum(e['task_return'] for e in episodes),
        'components':{key:sum(b.get('components', {}).get(key, 0.0) for b in collections)
                      for key in experiment.training.reward.components}}
    if full_run:
        report['summary'].update(task='full_run', abandoned=sum(outcome(e)=='abandoned' for e in episodes),
            genuine_start_attempts=sum(e.get('evidence')=='headless_rollout' for e in episodes),
            controlled_attempts=sum(e.get('evidence')=='controlled_fixture' for e in episodes))
        if experiment.training.reward.episode_goal == 'act1':
            clears = sum(e.get('act1_cleared') is True for e in episodes)
            report['summary'].update(goal='act1', act1_clears=clears,
                act1_clear_rate=clears/len(episodes) if episodes else None)
    report['summary']['decisions_per_second'] = report['summary']['accepted_decisions']/report['total_seconds']
    _publish_json(report_path, report)
    report_progress(report_path, report)
    return report_path, report
