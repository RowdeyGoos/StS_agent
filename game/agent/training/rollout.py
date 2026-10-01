"""Synchronous, frozen-policy combat collection with closed episode boundaries."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

import numpy as np
import torch

from game.agent import contracts as c
from game.agent.action_policy import ALL_LEGAL
from game.agent.encoding.full import FullRunEncoder
from game.agent.gym_env import FullRunEnv
from game.agent.provenance import implementation
from game.agent.progress import completed_act
from game.agent.recording import Metadata, COMPRESSED_SUFFIX as SUFFIX, TrajectoryWriter
from game.agent.trace_storage import trajectory_digest
from game.agent.runner import RunCancelled, prepare_directories
from .env import CombatTrainingEnv
from .features import FeatureEncoder, _RolloutEncoder
from .model import collate, policy_statistics, sample_actions
from .records import CombatTrainingRecorder
from .rewards import ACT_RUN_SCHEMA, SHAPED_RUN_SCHEMAS, measure_act_run, measure_full_run, measure_run
from .run_task import FullRunTrainingEnv
from .scenarios import SCENARIO_SET, episode_seed


def fingerprint(model):
    digest = hashlib.sha256(model.vocabulary.identity.encode())
    digest.update(repr(model.architecture).encode())
    if model.action_policy != ALL_LEGAL:
        digest.update(model.action_policy.encode())
    for name, value in model.state_dict().items():
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return ('sts_policy_state_v2:' if model.action_policy != ALL_LEGAL else 'sts_policy_state_v1:') + digest.hexdigest()


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise RunCancelled('PPO cancelled; resume the last complete batch checkpoint')


@dataclass(frozen=True, slots=True)
class RolloutStep:
    state: object
    candidate_refs: tuple[str, ...]
    mask: tuple[bool, ...]
    action: int
    old_log_probability: float
    value: float
    next_value: float
    reward: float
    components: dict
    terminated: bool
    truncated: bool
    episode_id: str
    episode_step: int
    reward_context: dict | None = None


@dataclass(frozen=True, slots=True)
class Rollout:
    steps: tuple[RolloutStep, ...]
    behavior: str
    iteration: int
    experiment: str
    next_episode: int
    progress: dict


def advantages(steps, *, gamma=1.0, gae_lambda=.95):
    """Bootstrap cutoffs, but recurse only within the same unfinished episode."""
    if not steps or not 0 < gamma <= 1 or not 0 <= gae_lambda <= 1:
        raise ValueError('Invalid GAE inputs')
    result, carry = [0.0]*len(steps), 0.0
    for i in range(len(steps)-1, -1, -1):
        step = steps[i]
        if (type(step.terminated) is not bool or type(step.truncated) is not bool or
                step.terminated and step.truncated or not all(math.isfinite(x) for x in
                (step.reward, step.value, step.next_value, step.old_log_probability)) or
                step.terminated and step.next_value != 0):
            raise ValueError('Invalid rollout flags or values')
        ended = step.terminated or step.truncated
        if not ended and (i+1 == len(steps) or steps[i+1].episode_id != step.episode_id or
                          steps[i+1].episode_step != step.episode_step+1):
            raise ValueError('Rollout must explicitly close every episode segment')
        delta = step.reward + gamma*(0 if step.terminated else step.next_value) - step.value
        carry = delta + (0 if ended else gamma*gae_lambda*carry)
        if not math.isfinite(carry):
            raise ValueError('Nonfinite GAE result')
        result[i] = carry
    adv = torch.tensor(result, dtype=torch.float32)
    returns = torch.tensor([a+s.value for a,s in zip(result, steps)], dtype=torch.float32)
    if not torch.isfinite(adv).all() or not torch.isfinite(returns).all():
        raise ValueError('GAE exceeds finite model precision')
    return adv, returns


def collect(model, experiment, generator, *, cursor, iteration, decisions=None,
            output_dir=None, audit_dir=None, env_factory=None, cancel=None, deadline=None, progress=None,
            encounter_cursor=None, encounter_stride=1):
    """No environment survives this call. Quota cutoffs retain their final state.

    Custom factories are trusted test/experiment code and require a distinct
    public source identity. Seeds and collection cursors never enter features.
    """
    from .checkpoint import publish
    config = experiment.ppo
    if model.action_policy != experiment.training.action_policy:
        raise ValueError('Collection policy-action version differs from experiment')
    objective = experiment.training.reward
    full_run = objective.task == 'full_run'
    quota = config.rollout_steps if decisions is None else decisions
    if type(quota) is not int or not 1 <= quota <= config.rollout_steps:
        raise ValueError('Invalid bounded collection quota')
    episode_seed('train', cursor)
    if (encounter_cursor is not None and (type(encounter_cursor) is not int or encounter_cursor < 0) or
            type(encounter_stride) is not int or encounter_stride < 1):
        raise ValueError('Invalid collection encounter schedule')
    if (env_factory is None) != (experiment.source == SCENARIO_SET):
        raise ValueError('Custom collection requires a distinct source and an explicit environment factory')
    from .combat_corpus import CorpusEnvironment, validate_factory
    validate_factory(experiment, env_factory)
    if output_dir is not None:
        output, audit = prepare_directories(output_dir, audit_dir)
    else:
        output = audit = None
    identity, behavior = implementation(), fingerprint(model)
    identity = replace(identity, policy='ppo_v1:' + behavior.split(':')[-1])
    encoder = FeatureEncoder(model.vocabulary, action_policy=model.action_policy)
    prepared = None
    model.eval()
    steps, episodes = [], []
    progress = {} if progress is None else progress
    progress.update(status='collecting', episodes=episodes, steps=0, stop_reason=None,
                    components=dict.fromkeys(objective.components, 0.0))
    before = time.perf_counter()
    def expired():
        return deadline is not None and time.monotonic() >= deadline
    def infer(public):
        state = encoder.encode(public) if prepared is None else prepared.features_for(public)
        batch = collate([state], vocabulary=model.vocabulary)
        with torch.inference_mode():
            logits, value = model(batch)
        if not torch.isfinite(value).all():
            raise ValueError('Nonfinite rollout value')
        return state, batch, logits, value.item()
    try:
        while len(steps) < quota:
            check_cancel(cancel)
            if expired():
                progress['stop_reason'] = 'time_budget'
                break
            name = experiment.encounters[(cursor if encounter_cursor is None else encounter_cursor) % len(experiment.encounters)]
            if encounter_cursor is not None:
                encounter_cursor += encounter_stride
            seed = episode_seed('train', cursor)
            cursor += 1
            limit = min(config.episode_decisions, quota-len(steps))
            episode_id = uuid.uuid4().hex
            row = {'episode_id':episode_id, 'encounter':name, 'status':'failed', 'steps':0,
                   'task_return':0.0, 'combat':None, 'potion_use_actions':0}
            episodes.append(row)
            settings = dict(encounter=name, reward_spec=experiment.training.reward,
                            max_decisions=limit, time_limit_seconds=config.episode_seconds)
            with ExitStack() as stack:
                env = stack.enter_context(CombatTrainingEnv(**settings) if env_factory is None else env_factory(**settings))
                # Custom environments/encoders keep their independent encoding
                # contract. Standard tasks can reuse the graph built by Gym.
                prepared = None
                if (type(env) in (CombatTrainingEnv, FullRunEnv, FullRunTrainingEnv) and
                        type(env.encoder) is FullRunEncoder and env.encoder.profile == encoder.public.profile):
                    prepared = _RolloutEncoder(encoder)
                    env.encoder = prepared
                    stack.callback(prepared.clear)
                observation, info = env.reset(seed=seed)
                public, summary = env.public_state, info.get('combat')
                if isinstance(public, c.RunOutcome):
                    raise ValueError('Collection requires an initial ready decision')
                row['start_hp'] = public.run.get('hp') if full_run else summary['hp']
                row['contexts'], row['action_kinds'] = {}, {}
                from .run_task import environment as campaign_environment
                corpus_start = type(env_factory) is CorpusEnvironment
                row['evidence'] = ('headless_rollout' if full_run and env_factory is campaign_environment
                                   or corpus_start else 'controlled_fixture')
                if corpus_start:
                    row.update(case_id=env.corpus_case['case_id'], source_group=env.corpus_case['source_group'],
                               public_state_sha256=env.corpus_case['public_state_sha256'],
                               encounter=env.corpus_case['encounter'], room_kind=env.corpus_case['room_kind'],
                               start_kind=env.corpus_case['start_kind'], start_turn=env.corpus_case['turn'])
                writer = None
                if output is not None:
                    replay = {'schema':'sts_ppo_episode_replay_v1', 'environment_reset_seed':seed,
                              'encounter':name, 'source':experiment.source, 'episode_decisions':limit,
                              'episode_seconds':config.episode_seconds, 'behavior':behavior,
                              'experiment':experiment.to_dict()}
                    publish(audit/(episode_id+'.audit.json'), json.dumps(replay, sort_keys=True,
                        allow_nan=False).encode(), private=True)
                    metadata = Metadata.create(identity, episode_id=episode_id,
                        scenario=experiment.source+':'+name, split='train', evidence=row['evidence'])
                    public_owner = None if prepared is None else prepared.prepared_for(public)
                    writer = stack.enter_context(TrajectoryWriter(output/(episode_id+SUFFIX), metadata, public,
                            prepared=public_owner)
                        if full_run else CombatTrainingRecorder(output/(episode_id+SUFFIX),
                            metadata, public, summary, reward_spec=objective, prepared=public_owner))
                current = None
                while True:
                    check_cancel(cancel)
                    state, batch, logits, value = current if current is not None else infer(public)
                    if expired():
                        terminated, truncated = False, True
                        outcome = c.RunOutcome('sts_run_outcome_v1', 'truncated', 'time_budget')
                        progress['stop_reason'] = 'time_budget'
                        if row['steps']:
                            steps[-1] = replace(steps[-1], truncated=True, next_value=value)
                        break
                    count = len(state.graph.candidate_refs)
                    if (not np.array_equal(observation['action_mask'][:count], state.graph.observation['action_mask']) or
                            observation['action_mask'][count:].any() or not np.array_equal(
                            observation['candidates'][:count], state.graph.observation['candidates'])):
                        raise ValueError('Policy and environment candidate mappings disagree')
                    with torch.inference_mode():
                        action = sample_actions(logits, batch['mask'], generator=generator)
                        logp, _ = policy_statistics(logits, batch['mask'], action)
                    index = action.item()
                    chosen = next(a for a in public.candidates if a.ref == state.graph.candidate_refs[index])
                    context = public.context.kind
                    prior_act = completed_act(public)
                    observation, reward, terminated, truncated, info = env.step(index)
                    execution = info['execution']
                    if execution is None:
                        if not truncated or terminated or reward != 0:
                            raise ValueError('Missing execution outside an action-free cutoff')
                        outcome = c.from_dict(info['outcome'])
                        if row['steps']:
                            steps[-1] = replace(steps[-1], truncated=True, next_value=value)
                        progress['stop_reason'] = 'time_budget'
                        break
                    if execution['status'] != 'reconciled':
                        raise ValueError('PPO requires a reconciled action; no retry is allowed')
                    public, summary = env.public_state, info.get('combat')
                    measurement = ({'spec_id':objective.identity, 'components':asdict(measure_run(public))}
                                   if full_run and objective.schema not in SHAPED_RUN_SCHEMAS else info.get('training_reward'))
                    if measurement is None or measurement['spec_id'] != objective.identity:
                        raise ValueError('Missing/mixed rollout reward objective')
                    if objective.schema in SHAPED_RUN_SCHEMAS:
                        reward_context = measurement.get('context')
                        act_rewards = objective.schema == ACT_RUN_SCHEMA
                        keys = {'before_combat','after_combat'} | ({'before_act'} if act_rewards else set())
                        if type(reward_context) is not dict or set(reward_context) != keys:
                            raise ValueError('Full-run reward lacks matching public measurements')
                        if act_rewards and reward_context['before_act'] != prior_act:
                            raise ValueError('Previous act marker differs from the public observation')
                        measured = (measure_act_run(chosen, c.from_dict(execution), public,
                            reward_context['before_combat'], reward_context['after_combat'], prior_act) if act_rewards else
                            measure_full_run(chosen, c.from_dict(execution), public,
                                reward_context['before_combat'], reward_context['after_combat']))
                        if asdict(measured) != measurement['components']:
                            raise ValueError('Full-run reward lacks matching public measurements')
                    if objective.episode_goal == 'act1':
                        success = completed_act(public) == 1
                        if (info.get('act1_cleared') is not success or info.get('goal') != 'act1' or
                                success and (not terminated or truncated or info['outcome'] !=
                                    c.to_dict(c.RunOutcome('sts_run_outcome_v1','truncated','external_stop')))):
                            raise ValueError('Act 1 task boundary disagrees with its public completion')
                        row['act1_cleared'] = success
                    if reward != objective.evaluate(measurement['components']):
                        raise ValueError('Task reward disagrees with its public measurement')
                    current = None if terminated else infer(public)
                    next_value = 0.0 if terminated else current[3]
                    step = RolloutStep(state, state.graph.candidate_refs, tuple(batch['mask'][0].tolist()), index,
                        logp.item(), value, next_value, float(reward), dict(measurement['components']),
                        terminated, truncated, episode_id, row['steps'],
                        measurement.get('context') if objective.schema in SHAPED_RUN_SCHEMAS else None)
                    steps.append(step)
                    row['steps'] += 1
                    row['task_return'] += reward
                    row['potion_use_actions'] += int(chosen.kind == 'use_potion')
                    row['contexts'][context] = row['contexts'].get(context, 0) + 1
                    row['action_kinds'][chosen.kind] = row['action_kinds'].get(chosen.kind, 0) + 1
                    for key, amount in step.components.items():
                        progress['components'][key] += amount
                    progress['steps'] = len(steps)
                    if writer is not None:
                        public_owner = None if prepared is None else prepared.prepared_for(public)
                        if full_run:
                            writer.append(chosen, c.from_dict(execution), public, prepared=public_owner)
                        else:
                            writer.append(chosen, c.from_dict(execution), public, combat_summary=summary,
                                          reward=reward, terminated=terminated, truncated=truncated,
                                          prepared=public_owner)
                    if terminated or truncated:
                        outcome = c.from_dict(info['outcome'])
                        break
                row.update(status='terminated' if terminated else 'truncated', combat=summary,
                           outcome=c.to_dict(outcome),
                           end_hp=(public.run.get('hp') if hasattr(public, 'run') else None) if full_run else summary['hp'],
                           timings={} if full_run else env.timings)
                if writer is not None:
                    if full_run:
                        writer.finish(outcome, check_cancel=lambda:check_cancel(cancel))
                        row.update(trajectory=writer.path.name,
                                   trajectory_sha256=trajectory_digest(writer.path))
                    else:
                        writer.finish(outcome, combat_summary=summary, terminated=terminated, truncated=truncated,
                                      check_cancel=lambda:check_cancel(cancel))
                        row.update(trajectory=writer.writer.path.name, training=writer.path.name,
                                   trajectory_sha256=json.loads(writer.path.read_text())['trajectory_sha256'])
            # A timeout with no executed action cannot make quota progress. Stop
            # the collection rather than repeatedly resetting another game.
            if not row['steps'] or progress['stop_reason'] is not None:
                break
        if fingerprint(model) != behavior:
            raise ValueError('Policy changed while collecting a frozen rollout')
        if steps:
            advantages(steps, gamma=config.gamma, gae_lambda=config.gae_lambda)
        progress['status'] = 'complete'
        return Rollout(tuple(steps), behavior, iteration, experiment.identity, cursor, progress)
    except BaseException as error:
        progress['status'] = 'cancelled' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed'
        progress['failure'] = getattr(error, 'reason', type(error).__name__)
        raise
    finally:
        progress['seconds'] = time.perf_counter()-before
        progress['decisions_per_second'] = len(steps)/progress['seconds']
