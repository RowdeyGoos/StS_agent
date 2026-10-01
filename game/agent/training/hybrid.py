"""Paired bounded campaign feedback for a frozen combat-only checkpoint."""
from dataclasses import asdict
import json
from pathlib import Path
import time
import uuid

from game.agent import contracts as c
from game.agent.provenance import implementation
from game.agent.recording import load_trajectory
from game.agent.runner import RunConfig, prepare_directories, run_episode
from .checkpoint import load_policy, publish
from .scenarios import episode_seed


def evaluate_hybrid(*, checkpoint, output_dir, cases=2, split='validation', start_index=0,
                    max_decisions=256, time_limit_seconds=30.0, audit_dir=None):
    if type(cases) is not int or not 1 <= cases <= 100:
        raise ValueError('Choose 1–100 bounded development campaign cases')
    episode_seed(split, start_index)
    episode_seed(split, start_index+cases-1)
    learned = load_policy(checkpoint, task='combat')
    output = Path(output_dir).resolve()
    output, audit = prepare_directories(output, audit_dir or output.with_name(output.name+'-private'))
    path = output/'hybrid.json'
    if path.exists() or path.with_name(path.name+'.partial').exists():
        raise FileExistsError(path)
    identity = implementation()
    fingerprint = 'hybrid_v1:' + learned.identity.split(':')[-1] + ':' + identity.policy
    report = {'schema': 'sts_hybrid_campaign_v1', 'status': 'complete', 'split': split,
              'implementation': asdict(identity), 'checkpoint': learned.identity,
              'reward_spec': learned.reward_spec.to_dict(), 'evidence': 'headless_rollout',
              'limits': {'max_decisions': max_decisions, 'time_limit_seconds': time_limit_seconds},
              'requested_episodes': cases*2, 'episodes': []}
    started = time.perf_counter()
    for index in range(start_index, start_index+cases):
        pair = uuid.uuid4().hex
        for name in ('heuristic', 'hybrid'):
            episode_id = uuid.uuid4().hex
            row = {'episode_id': episode_id, 'pair_id': pair, 'policy': name, 'status': 'failed'}
            report['episodes'].append(row)
            try:
                config = RunConfig(seed=episode_seed(split, index), split=split,
                                   max_decisions=max_decisions, time_limit_seconds=time_limit_seconds)
                result = run_episode(config, output_dir=output, audit_dir=audit, episode_id=episode_id,
                    combat_policy=learned if name == 'hybrid' else None,
                    policy_identity=fingerprint if name == 'hybrid' else identity.policy)
                trajectory = load_trajectory(result.trajectory, split=split)
                last = trajectory.transitions[-1] if trajectory.transitions else None
                decision = (last.successor if last and not isinstance(last.successor, c.RunOutcome)
                            else last.observation if last else trajectory.initial)
                progress = {key: decision.run.get(key) for key in ('act', 'floor', 'hp', 'max_hp')}
                row.update(status='complete', trajectory=Path(result.trajectory).name,
                    outcome=c.to_dict(result.outcome), steps=len(trajectory.transitions),
                    last_public_hud=progress,
                    potion_use_actions=sum(t.action.kind == 'use_potion' for t in trajectory.transitions),
                    timings=asdict(result.timings))
            except (Exception, KeyboardInterrupt) as error:
                row['failure'] = type(error).__name__
                report['status'] = 'failed'
                break
        if report['status'] != 'complete':
            break
    report['unattempted_episodes'] = report['requested_episodes']-len(report['episodes'])
    report['total_seconds'] = time.perf_counter()-started
    publish(path, (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report
