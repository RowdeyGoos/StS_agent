"""Bounded reference-policy evaluation with public trajectories and task sidecars."""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from random import Random
import time
import uuid

from game.agent import contracts as c
from game.agent.action_policy import action_mask
from game.agent.full_policy import choose_action
from game.agent.provenance import implementation
from game.agent.recording import Metadata, COMPRESSED_SUFFIX as SUFFIX
from game.agent.runner import RunCancelled, prepare_directories
from .config import TrainingConfig
from .env import CombatTrainingEnv
from .records import CombatTrainingRecorder
from .rewards import COMPONENTS
from .scenarios import SCENARIO_SET, SCENARIOS, SEED_SCHEDULE, episode_seed, scenario


@dataclass(frozen=True, slots=True)
class BaselineCase:
    encounter: str
    split: str
    seed: int
    policy_seed: int
    max_decisions: int
    time_limit_seconds: float


def _audit(path, case, identity, policy, config, scenario_set=SCENARIO_SET):
    value = {'schema': 'sts_combat_replay_v2', 'config': asdict(case),
             'training_config': config.to_dict(), 'reward_spec_id': config.reward.identity,
             'scenario_set': scenario_set, 'seed_schedule': SEED_SCHEDULE,
             'policy': policy, 'implementation': asdict(identity)}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        json.dump(value, target, sort_keys=True, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def _episode(case, policy, identity, output, audit, config, *, chooser=None,
             engine_factory=None, scenario_set=SCENARIO_SET, cancel=None,
             episode_id=None, expected_start=None, evidence='controlled_fixture'):
    episode_id = uuid.uuid4().hex if episode_id is None else episode_id
    path = output / (episode_id + SUFFIX)
    result = {'episode_id': episode_id, 'encounter': case.encounter, 'policy': policy,
              'status': 'failed', 'trajectory': None, 'training': None, 'combat': None,
              'steps': 0, 'end_turn_actions': 0, 'potion_use_actions': 0,
              'task_return': 0.0, 'run_outcome': None, 'failure': None,
              'reward_spec_id': config.reward.identity, 'components': dict.fromkeys(COMPONENTS, 0.0)}
    recording = policy_seconds = 0.0
    started = time.perf_counter()
    env = CombatTrainingEnv(encounter=case.encounter, max_decisions=case.max_decisions,
                            time_limit_seconds=case.time_limit_seconds, reward_spec=config.reward,
                            engine_factory=engine_factory)
    try:
        _audit(audit / (episode_id + '.audit.json'), case, identity, policy, config, scenario_set)
        observation, info = env.reset(seed=case.seed)
        if expected_start is not None:
            from .combat_corpus import public_digest
            result['public_state_sha256'] = public_digest(env.public_state)
            if result['public_state_sha256'] != expected_start:
                raise ValueError('Combat initial public state differs from its frozen case')
        result['observation_bytes'] = sum(value.nbytes for value in observation.values())
        result['start_hp'] = info['combat']['hp']
        result['start_max_hp'] = info['combat']['max_hp']
        metadata = Metadata.create(identity, episode_id=episode_id,
                                   scenario=scenario_set + ':' + case.encounter,
                                   split=case.split, evidence=evidence)
        before = time.perf_counter()
        writer = CombatTrainingRecorder(path, metadata, env.public_state, info['combat'],
                                         reward_spec=config.reward)
        recording += time.perf_counter() - before
        rng = Random(case.policy_seed)  # Policy RNG never consumes the engine RNG.
        with writer:
            for _ in range(case.max_decisions):
                if cancel is not None and cancel.is_set():
                    raise RunCancelled('Evaluation cancelled')
                public = env.public_state
                before = time.perf_counter()
                allowed = tuple(a for a, permitted in zip(public.candidates,
                    action_mask(public, config.action_policy)) if permitted)
                chosen = (chooser(public) if chooser is not None else rng.choice(allowed)
                          if policy == 'random_legal' else choose_action(public))
                if chosen not in allowed:
                    raise ValueError('Evaluation chooser violated its configured action policy')
                policy_seconds += time.perf_counter() - before
                _, reward, terminated, truncated, info = env.step(env.action_index(chosen))
                report = info['execution']
                if report is not None:
                    execution = c.from_dict(report)
                    if execution.status != 'reconciled':
                        raise RuntimeError('Baseline selected an unreconciled action')
                    before = time.perf_counter()
                    writer.append(chosen, execution, env.public_state, combat_summary=info['combat'],
                                  reward=reward, terminated=terminated, truncated=truncated)
                    recording += time.perf_counter() - before
                    result['steps'] += 1
                    result['end_turn_actions'] += int(chosen.kind == 'end_turn')
                    result['potion_use_actions'] += int(chosen.kind == 'use_potion')
                    for name, value in info['training_reward']['components'].items():
                        result['components'][name] += value
                result['task_return'] += reward
                result['combat'] = info['combat']
                if terminated or truncated:
                    outcome = c.from_dict(info['outcome'])
                    before = time.perf_counter()
                    writer.finish(outcome, combat_summary=info['combat'],
                                  terminated=terminated, truncated=truncated)
                    recording += time.perf_counter() - before
                    result.update(status='terminated' if terminated else 'truncated',
                                  trajectory=path.name, training=writer.path.name, run_outcome=info['outcome'])
                    break
            else:
                raise RuntimeError('Combat environment failed to enforce its decision budget')
    except (Exception, KeyboardInterrupt) as error:
        # Stop this evaluation after a failure. No action is retried, and the
        # incomplete trajectory remains .partial. Do not dump private state.
        result['failure'] = getattr(error, 'reason', type(error).__name__)
        if isinstance(error, (KeyboardInterrupt, RunCancelled)):
            result['status'] = 'interrupted'
    finally:
        result['end_hp'] = (result.get('combat') or {}).get('hp')
        result['timings'] = {**env.timings, 'policy_seconds': policy_seconds,
                             'recording_seconds': recording,
                             'total_seconds': time.perf_counter() - started}
        env.close()
    return result


def _summary(rows):
    count = len(rows)
    wins = [r for r in rows if r['status'] == 'terminated' and r['combat']['outcome'] == 'victory']
    losses = sum(r['status'] == 'terminated' and r['combat']['outcome'] == 'defeat' for r in rows)
    rate = len(wins) / count if count else None
    # Wilson interval includes cutoffs/failures as unsuccessful attempts.
    interval = None
    if count:
        z = 1.959963984540054
        denominator = 1 + z*z/count
        center = (rate + z*z/(2*count)) / denominator
        half = z * math.sqrt(rate*(1-rate)/count + z*z/(4*count*count)) / denominator
        interval = [max(0.0, center-half), min(1.0, center+half)]
    timings = {key: sum(r['timings'].get(key, 0.0) for r in rows)
               for key in ('initialization_seconds', 'simulation_dispatch_seconds', 'projection_seconds',
                           'encoding_seconds', 'policy_seconds', 'recording_seconds', 'total_seconds')}
    steps = sum(r['steps'] for r in rows)
    return {'attempted': count, 'wins': len(wins), 'losses': losses,
            'cutoffs': sum(r['status'] == 'truncated' for r in rows),
            'failures': sum(r['status'] in ('failed', 'interrupted') for r in rows),
            'win_rate': rate, 'win_rate_wilson_95': interval,
            'mean_hp_on_win': sum(r['combat']['hp'] for r in wins)/len(wins) if wins else None,
            'mean_task_return': sum(r['task_return'] for r in rows)/count if count else None,
            'component_totals': {name: sum(r['components'][name] for r in rows) for name in COMPONENTS},
            'steps': steps, 'timings': timings,
            'decisions_per_second': steps/timings['total_seconds'] if timings['total_seconds'] else None}


def evaluate_baselines(*, output_dir, audit_dir=None, cases_per_scenario=4,
                       split='validation', start_index=0, encounters=None,
                       max_decisions=256, time_limit_seconds=30.0, config=None, checkpoint=None):
    """Compare both reference policies on the same cases; reserve test for later.

    Explicit callers can evaluate any split. The default uses development cases
    and leaves held-out test seeds untouched. The report includes failures and
    cutoffs; an infrastructure failure stops the batch and identifies omissions.
    """
    config = TrainingConfig() if config is None else config
    if type(config) is not TrainingConfig:
        raise ValueError('config must be a TrainingConfig')
    if type(cases_per_scenario) is not int or not 1 <= cases_per_scenario <= 10000:
        raise ValueError('cases_per_scenario must be between 1 and 10000')
    episode_seed(split, start_index)
    episode_seed(split, start_index + cases_per_scenario - 1)
    selected = tuple(SCENARIOS) if encounters is None else tuple(scenario(n) for n in encounters)
    if not selected or len({s.encounter for s in selected}) != len(selected):
        raise ValueError('Choose distinct nonempty scenarios')
    # Validate budgets before creating any artifacts.
    with CombatTrainingEnv(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds):
        pass
    output = Path(output_dir).resolve()
    output, audit = prepare_directories(output, audit_dir or output.with_name(output.name + '-private'))
    path = output / 'baseline.json'
    partial = path.with_name(path.name + '.partial')
    if path.exists():
        raise FileExistsError(path)
    identity = implementation()
    policies = {'random_legal': 'random_legal_v1:' + identity.build, 'heuristic': identity.policy}
    learned = None
    if checkpoint is not None:
        from .checkpoint import load_policy
        learned = load_policy(checkpoint, reward_spec=config.reward)
        policies[learned.algorithm] = learned.identity
    import gymnasium
    import numpy
    report = {'schema': 'sts_combat_baseline_v2', 'created_at': datetime.now(timezone.utc).isoformat(),
              'training_config': config.to_dict(), 'reward_spec_id': config.reward.identity,
              'status': 'complete', 'scenario_set': SCENARIO_SET, 'evidence': 'controlled_fixture',
              'split': split, 'cases_per_scenario': cases_per_scenario,
              'scenarios': [asdict(s) for s in selected], 'policies': policies,
              'implementation': asdict(identity),
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(),
                          'gymnasium': gymnasium.__version__, 'numpy': numpy.__version__},
              'limits': {'max_decisions': max_decisions, 'time_limit_seconds': time_limit_seconds},
              'timing_definitions': {
                  'initialization_seconds': 'Scenario construction and initial combat setup',
                  'simulation_dispatch_seconds': 'Action dispatch, including guards, engine simulation and history',
                  'projection_seconds': 'Public observation, including its ownership/state guard',
                  'encoding_seconds': 'Fixed Gym encoding; excludes returned-array copies',
                  'recording_seconds': 'Canonical trajectory and training sidecar validation, serialization and publication',
                  'total_seconds': 'Episode wall time, including replay audit and array copies'},
              'requested_episodes': len(selected)*cases_per_scenario*len(policies), 'episodes': []}
    # Reserve the publication path before running; concurrent/duplicate runs
    # cannot overwrite it. Failures leave valid episodes and an explicit report.
    with partial.open('x', encoding='utf-8') as target:
        stop = False
        for item in selected:
            for index in range(start_index, start_index + cases_per_scenario):
                seed = episode_seed(split, index)
                policy_seed = int.from_bytes(hashlib.sha256(
                    f'random_legal_v1:{seed}:{item.encounter}'.encode()).digest()[:8], 'big')
                case = BaselineCase(item.encounter, split, seed, policy_seed, max_decisions, time_limit_seconds)
                pair_id = uuid.uuid4().hex  # Public grouping without a seed/index.
                for policy, fingerprint in policies.items():
                    row = _episode(case, policy, replace(identity, policy=fingerprint), output, audit, config,
                                   chooser=learned if learned is not None and policy == learned.algorithm else None)
                    row['pair_id'] = pair_id
                    report['episodes'].append(row)
                    if row['status'] in ('failed', 'interrupted'):
                        report['status'], stop = row['status'], True
                        break
                if stop:
                    break
            if stop:
                break
        report['unattempted_episodes'] = report['requested_episodes'] - len(report['episodes'])
        report['summary'] = {policy: _summary([r for r in report['episodes'] if r['policy'] == policy])
                             for policy in policies}
        report['by_encounter'] = {s.encounter: {
            policy: _summary([r for r in report['episodes'] if r['policy'] == policy and r['encounter'] == s.encounter])
            for policy in policies} for s in selected}
        json.dump(report, target, indent=2, sort_keys=True, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())
    os.link(partial, path)
    partial.unlink()
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report
