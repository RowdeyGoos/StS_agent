"""Canonical full-run demonstrations and explicit combat-to-run weight transfer."""
from collections import deque
import hashlib
import json
import time

import torch

from game.agent.recording import load_trajectory
from game.agent.action_policy import ALL_LEGAL, validate_policy
from .config import RUN_SCENARIO_SET
from .features import FeatureEncoder, Vocabulary
from .learner import Corpus, Example
from .model import ActorCritic
from .rewards import RewardSpec, measure_run


def load_run_corpus(paths, *, split, vocabulary=None, base_vocabulary=None, action_policy=ALL_LEGAL):
    validate_policy(action_policy)
    from .run_demonstrations import _LoadedRunPaths
    if vocabulary is None and split != 'train' or base_vocabulary is not None and (split != 'train' or vocabulary is not None):
        raise ValueError('Fit/expand vocabulary on train only; evaluation requires frozen vocabulary')
    episodes = (paths.consume(split) if type(paths) is _LoadedRunPaths else
                deque(load_trajectory(path, split=split) for path in paths))
    del paths
    seen = set()
    for episode in episodes:
        if episode.metadata.split != split:
            raise ValueError('Dataset split mismatch')
        if episode.sha256 in seen:
            raise ValueError('Duplicate run demonstration')
        seen.add(episode.sha256)
        if not episode.metadata.scenario.startswith(RUN_SCENARIO_SET+':'):
            raise ValueError('Run corpus requires explicitly declared full-run task records')
    if vocabulary is None:
        vocabulary = Vocabulary.fit((s.observation for e in episodes for s in e.transitions), split='train')
        if base_vocabulary is not None:
            vocabulary = Vocabulary(tuple(sorted(set(vocabulary.names) | set(base_vocabulary.names))))
    encoder, objective = FeatureEncoder(vocabulary, action_policy=action_policy), RewardSpec.full_run()
    examples, hashes, seconds = [], [], 0.0
    while episodes:
        # Release parsed observations as compact examples take their place.
        episode = episodes.popleft()
        hashes.append(episode.sha256)
        # Assisted room/campaign fixtures teach actions, never natural-start
        # victory probability. Cutoffs likewise have no Monte Carlo label.
        labelled = episode.outcome.kind != 'truncated' and episode.metadata.evidence == 'headless_rollout'
        returns, total = [], 0.0
        for step in reversed(episode.transitions):
            reward = objective.evaluate(measure_run(step.successor))
            if reward != step.reward:
                raise ValueError('Noncanonical run reward')
            total += reward
            returns.append(total if labelled else None)
        before = time.perf_counter()
        for step, target in zip(episode.transitions, reversed(returns)):
            state = encoder.encode(step.observation)
            action = state.graph.candidate_refs.index(step.action.ref)
            if not state.policy_mask[action]:
                raise ValueError('Demonstration action is excluded by the declared action policy')
            examples.append(Example(state, action, target))
        seconds += time.perf_counter()-before
    if not examples:
        raise ValueError('Full-run corpus has no reconciled decisions')
    bindings = [vocabulary.identity, objective.identity, hashes]
    if action_policy != ALL_LEGAL:
        bindings.append(action_policy)
    identity = 'sts_full_run_corpus_v1:'+hashlib.sha256(json.dumps(bindings, separators=(',', ':')).encode()).hexdigest()
    return Corpus(tuple(examples), vocabulary, objective, identity, split, len(hashes), seconds, action_policy)


def transfer_combat(policy, vocabulary, *, seed=0, action_policy=None):
    """Transfer actor/shared layers by identity; fresh value head and optimizer."""
    old = policy.model
    if policy.reward_spec.task != 'combat' or not set(old.vocabulary.names) <= set(vocabulary.names):
        raise ValueError('Combat transfer requires an expanded training vocabulary')
    model = ActorCritic(vocabulary, old.architecture, seed=seed,
        action_policy=old.action_policy if action_policy is None else action_policy)
    state, source = model.state_dict(), old.state_dict()
    for key in state:
        if key != 'name.weight' and not key.startswith('value.'):
            state[key] = source[key].clone()
    ids = {name:i+1 for i,name in enumerate(vocabulary.names)}
    state['name.weight'][0] = source['name.weight'][0]
    for i, name in enumerate(old.vocabulary.names, 1):
        state['name.weight'][ids[name]] = source['name.weight'][i]
    model.load_state_dict(state, strict=True)
    # Zero initial return prediction, with a freshly initialized hidden layer.
    # No combat value predictions or optimizer momentum enter the run task.
    with torch.no_grad():
        model.value[-1].weight.zero_()
        model.value[-1].bias.zero_()
    lineage = {'kind':'combat_actor_transfer_v1', 'source_checkpoint':policy.identity,
        'source_objective':policy.reward_spec.identity, 'source_vocabulary':old.vocabulary.identity,
        'target_vocabulary':vocabulary.identity, 'retained_names':len(old.vocabulary.names),
        'new_train_names':len(vocabulary.names)-len(old.vocabulary.names),
        'value_head':'fresh_hidden_zero_output', 'optimizer_rng_cursor':'fresh'}
    return model, lineage


def transfer_run_objective(policy, reward_spec, *, seed=0):
    """Explicit new full-run experiment: retain actor, reset changed critic."""
    if (type(reward_spec) is not RewardSpec or reward_spec.task != 'full_run' or
            policy.reward_spec.task != 'full_run' or policy.reward_spec == reward_spec):
        raise ValueError('Objective reset requires different full-run reward specifications')
    old = policy.model
    model = ActorCritic(old.vocabulary, old.architecture, seed=seed, action_policy=old.action_policy)
    state = model.state_dict()
    for key, tensor in old.state_dict().items():
        if not key.startswith('value.'):
            state[key] = tensor.clone()
    model.load_state_dict(state, strict=True)
    with torch.no_grad():
        model.value[-1].weight.zero_()
        model.value[-1].bias.zero_()
    return model, {'kind':'full_run_objective_transfer_v1', 'source_checkpoint':policy.identity,
        'source_objective':policy.reward_spec.to_dict(), 'target_objective':reward_spec.to_dict(),
        'actor_vocabulary':'retained_exactly', 'value_head':'fresh_hidden_zero_output',
        'optimizer_rng_cursor':'fresh'}
