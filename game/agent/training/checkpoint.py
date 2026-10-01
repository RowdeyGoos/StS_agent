"""Atomic inference bundles and separate owner-only CPU learner resume state."""
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import zipfile

import torch

from game.agent.contracts import full as f
from game.agent.action_policy import ALL_LEGAL, validate_policy
from game.agent.encoding.full import FULL_RUN_PROFILE
from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from .features import FeatureEncoder, Vocabulary
from .model import ActorCritic, Architecture, collate, log_probabilities
from .rewards import RewardSpec, strict_json

SCHEMA = 'sts_inference_bundle_v1'
PPO_SCHEMA = 'sts_inference_bundle_v2'
ACTION_SCHEMA = 'sts_inference_bundle_v3'
RESUME_SCHEMA = 'sts_imitation_resume_v1'
PPO_RESUME_SCHEMA = 'sts_ppo_resume_v3'
SUFFIX = '.sts-model'


def publish(path, data, *, private=False):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + '.partial')
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, 'wb') as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    os.link(partial, path)
    partial.unlink()
    return hashlib.sha256(data).hexdigest()


def runtime():
    return {'python': platform.python_version(), 'torch': str(torch.__version__),
            'threads': torch.get_num_threads(), 'device': 'cpu',
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled()}


def _tensor_bytes(value):
    target = io.BytesIO()
    torch.save(value, target)
    return target.getvalue()


def save_checkpoint(path, learner, *, resume_path=None):
    """The public bundle contains no optimizer, learner RNG or sampling cursor."""
    if learner.failed:
        raise ValueError('Cannot checkpoint a failed/in-flight update')
    path = Path(path)
    if not path.name.endswith(SUFFIX):
        raise ValueError('Use a .sts-model checkpoint filename')
    if resume_path is not None:
        prepare_directories(path.parent, Path(resume_path).parent)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    digest = _save_inference(path, learner.model, learner.corpus.reward_spec,
                             learner.updates, asdict(learner.config))
    if resume_path is not None:
        state = {'schema': RESUME_SCHEMA, 'bundle_sha256': digest, 'boundary': 'complete_corpus_update',
                 'corpus': learner.corpus.identity, 'config': asdict(learner.config),
                 'runtime': runtime(), 'optimizer': learner.optimizer.state_dict(),
                 'learner_rng': learner.generator.get_state(), 'order': learner.order,
                 'cursor': learner.cursor, 'updates': learner.updates}
        publish(resume_path, _tensor_bytes(state), private=True)
    return digest


def _save_inference(path, model, reward_spec, updates, settings, *, algorithm=None, resume_digest=None):
    weights = _tensor_bytes({key: value.detach().cpu() for key, value in model.state_dict().items()})
    if any(not torch.isfinite(value).all() for value in model.state_dict().values()):
        raise ValueError('Cannot publish nonfinite model weights')
    restricted = model.action_policy != ALL_LEGAL
    manifest = {'schema': ACTION_SCHEMA if restricted else SCHEMA if algorithm is None else PPO_SCHEMA,
                'contract': f.PROFILE, 'encoding': FULL_RUN_PROFILE.identity,
                'architecture': asdict(model.architecture), 'vocabulary': model.vocabulary.to_dict(),
                'feature_identity': model.vocabulary.identity, 'reward_spec': reward_spec.to_dict(),
                'reward_identity': reward_spec.identity, 'implementation': asdict(implementation()),
                'runtime': runtime(), 'updates': updates, 'learner_config': settings,
                'weights_sha256': hashlib.sha256(weights).hexdigest()}
    if restricted:
        manifest.update(action_policy=model.action_policy, algorithm=algorithm or 'imitation')
    if algorithm is not None:
        manifest['algorithm'] = algorithm
        manifest['resume_state_sha256'] = resume_digest
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, sort_keys=True, allow_nan=False))
        archive.writestr('weights.pt', weights)
    return publish(path, buffer.getvalue())


class CheckpointPolicy:
    def __init__(self, model, reward_spec, identity, manifest):
        self.model, self.reward_spec, self.identity, self.manifest = model, reward_spec, identity, manifest
        self.algorithm = manifest.get('algorithm', 'imitation')
        self.encoder = FeatureEncoder(model.vocabulary, action_policy=model.action_policy)
        self.model.eval().requires_grad_(False)

    def probabilities(self, decision):
        state = self.encoder.encode(decision)
        batch = collate([state], vocabulary=self.model.vocabulary)
        with torch.inference_mode():
            logits, value = self.model(batch)
            probabilities = log_probabilities(logits, batch['mask']).exp()[0].tolist()
        if not torch.isfinite(value).all():
            raise ValueError('Nonfinite checkpoint value')
        return dict(zip(state.graph.candidate_refs, probabilities)), value.item()

    def __call__(self, decision):
        probabilities, _ = self.probabilities(decision)
        ref = max(probabilities, key=probabilities.__getitem__)
        return next(a for a in decision.candidates if a.ref == ref)


def load_policy(path, *, expected_sha256=None, reward_spec=None, task=None):
    path = Path(path)
    if not path.name.endswith(SUFFIX) or path.stat().st_size > 128*1024*1024:
        raise ValueError('Expected a published bounded inference bundle')
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Checkpoint changed after evaluation was frozen')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if (sorted(archive.namelist()) != ['manifest.json', 'weights.pt'] or
                any(i.file_size > 64*1024*1024 for i in archive.infolist())):
            raise ValueError('Unsupported inference bundle entries')
        manifest = strict_json(archive.read('manifest.json'))
        weights = archive.read('weights.pt')
    required = {'schema', 'contract', 'encoding', 'architecture', 'vocabulary', 'feature_identity',
                'reward_spec', 'reward_identity', 'implementation', 'runtime', 'updates', 'weights_sha256', 'learner_config'}
    if type(manifest) is dict and manifest.get('schema') == PPO_SCHEMA:
        required.update(('algorithm', 'resume_state_sha256'))
    if type(manifest) is dict and manifest.get('schema') == ACTION_SCHEMA:
        required.update(('algorithm', 'action_policy'))
        if manifest.get('algorithm') == 'ppo':
            required.add('resume_state_sha256')
    if (type(manifest) is not dict or set(manifest) != required or manifest['schema'] not in (SCHEMA, PPO_SCHEMA, ACTION_SCHEMA) or
            manifest['contract'] != f.PROFILE or manifest['encoding'] != FULL_RUN_PROFILE.identity or
            manifest['weights_sha256'] != hashlib.sha256(weights).hexdigest() or
            type(manifest['updates']) is not int or manifest['updates'] < 0):
        raise ValueError('Incompatible or corrupt inference manifest')
    action_policy = validate_policy(manifest.get('action_policy', ALL_LEGAL))
    if manifest['schema'] == ACTION_SCHEMA and (action_policy == ALL_LEGAL or
            manifest['algorithm'] not in ('imitation', 'ppo')):
        raise ValueError('Invalid versioned action-policy manifest')
    vocabulary = Vocabulary.from_dict(manifest['vocabulary'])
    objective = RewardSpec.from_dict(manifest['reward_spec'])
    if task is not None and objective.task != task:
        raise ValueError('Checkpoint task mismatch')
    if manifest.get('algorithm') == 'ppo' or manifest['schema'] == PPO_SCHEMA:
        from .ppo_config import PPOExperiment
        experiment = PPOExperiment.from_dict(manifest['learner_config'])
        if (manifest['algorithm'] != 'ppo' or type(manifest['resume_state_sha256']) is not str or
                len(manifest['resume_state_sha256']) != 64 or
                any(ch not in '0123456789abcdef' for ch in manifest['resume_state_sha256']) or
                experiment.training.reward != objective or experiment.training.action_policy != action_policy):
            raise ValueError('Invalid PPO inference configuration')
    if (vocabulary.identity != manifest['feature_identity'] or objective.identity != manifest['reward_identity'] or
            reward_spec is not None and reward_spec != objective):
        raise ValueError('Feature or objective identity mismatch')
    if type(manifest['architecture']) is not dict or set(manifest['architecture']) != set(Architecture.__dataclass_fields__):
        raise ValueError('Unsupported architecture fields')
    model = ActorCritic(vocabulary, Architecture(**manifest['architecture']), action_policy=action_policy)
    state = torch.load(io.BytesIO(weights), map_location='cpu', weights_only=True)
    expected = model.state_dict()
    if (type(state) is not dict or state.keys() != expected.keys() or any(
            type(v) is not torch.Tensor or v.dtype != expected[k].dtype or v.shape != expected[k].shape or
            not torch.isfinite(v).all() for k, v in state.items())):
        raise ValueError('Incompatible or nonfinite model weights')
    model.load_state_dict(state, strict=True)
    return CheckpointPolicy(model, objective, manifest.get('algorithm', 'imitation')+'_v1:' + digest, manifest)


def restore_learner(bundle_path, resume_path, corpus):
    from .learner import ImitationLearner, LearnerConfig
    path = Path(resume_path)
    if (not path.name.endswith('.resume.pt') or path.stat().st_mode & 0o077 or
            path.parent.stat().st_mode & 0o077 or path.stat().st_size > 128*1024*1024):
        raise ValueError('Expected a published owner-only bounded resume file')
    policy = load_policy(bundle_path, reward_spec=corpus.reward_spec)
    if policy.algorithm != 'imitation':
        raise ValueError('Expected an imitation checkpoint')
    if policy.model.action_policy != corpus.action_policy:
        raise ValueError('Imitation resume cannot change its policy-action version')
    if policy.manifest['implementation'] != asdict(implementation()):
        raise ValueError('Exact resume requires unchanged implementation sources')
    state = torch.load(path, map_location='cpu', weights_only=True)
    required = {'schema', 'bundle_sha256', 'boundary', 'corpus', 'config', 'runtime', 'optimizer',
                'learner_rng', 'order', 'cursor', 'updates'}
    if (type(state) is not dict or set(state) != required or state['schema'] != RESUME_SCHEMA or
            state['bundle_sha256'] != policy.identity.split(':')[-1] or state['boundary'] != 'complete_corpus_update' or
            state['corpus'] != corpus.identity or state['runtime'] != runtime() or
            type(state['updates']) is not int or state['updates'] != policy.manifest['updates']):
        raise ValueError('Incompatible resume boundary, corpus, runtime or bundle')
    if (type(state['config']) is not dict or set(state['config']) != set(LearnerConfig.__dataclass_fields__) or
            state['config'] != policy.manifest['learner_config']):
        raise ValueError('Invalid resume settings')
    config = LearnerConfig(**state['config'])
    order, cursor = state['order'], state['cursor']
    if (type(order) is not torch.Tensor or order.dtype != torch.int64 or
            order.shape != (len(corpus.examples),) or not torch.equal(order.sort().values, torch.arange(len(order))) or
            type(cursor) is not int or not 0 <= cursor <= len(order)):
        raise ValueError('Invalid resume sampling cursor')
    learner = ImitationLearner(policy.model, corpus, config)
    restore_adam(learner, state['optimizer'], state['updates'])
    try:
        learner.generator.set_state(state['learner_rng'])
    except (TypeError, RuntimeError) as error:
        raise ValueError('Invalid learner RNG state') from error
    learner.order, learner.cursor, learner.updates = order, cursor, state['updates']
    return learner


def restore_adam(learner, optimizer, updates):
    # load_state_dict otherwise silently overwrites the declared Adam options.
    if (type(optimizer) is not dict or set(optimizer) != {'state', 'param_groups'} or
            optimizer['param_groups'] != learner.optimizer.state_dict()['param_groups'] or
            type(optimizer['state']) is not dict):
        raise ValueError('Resume optimizer settings disagree with the learner configuration')
    parameters = list(learner.model.parameters())
    for key, values in optimizer['state'].items():
        if (type(key) is not int or not 0 <= key < len(parameters) or type(values) is not dict or
                set(values) != {'step', 'exp_avg', 'exp_avg_sq'}):
            raise ValueError('Invalid Adam state keys')
        parameter = parameters[key]
        for name in ('exp_avg', 'exp_avg_sq'):
            value = values[name]
            if (type(value) is not torch.Tensor or value.shape != parameter.shape or
                    value.dtype != parameter.dtype or not torch.isfinite(value).all() or
                    name == 'exp_avg_sq' and (value < 0).any()):
                raise ValueError('Invalid Adam moment shape, type or value')
        step = values['step']
        if (type(step) is not torch.Tensor or step.ndim != 0 or step.dtype != torch.float32 or
                not torch.isfinite(step) or step.item() != int(step.item()) or
                step.item() != updates):
            raise ValueError('Invalid Adam update counter')
    if set(optimizer['state']) != (set(range(len(parameters))) if updates else set()):
        raise ValueError('Missing optimizer state for the saved update')
    learner.optimizer.load_state_dict(optimizer)


def save_ppo_checkpoint(path, learner, *, resume_path):
    from .ppo import UPDATE_POLICY
    if learner.phase != 'boundary' or learner.pending is not None:
        raise ValueError('PPO checkpoints require a closed rollout/update boundary')
    path = Path(path)
    if not path.name.endswith(SUFFIX):
        raise ValueError('Use a .sts-model checkpoint filename')
    prepare_directories(path.parent, Path(resume_path).parent)
    state = {'schema':PPO_RESUME_SCHEMA, 'boundary':'closed_rollout_update',
             'update_policy':UPDATE_POLICY, 'skipped_iterations':learner.skipped_iterations,
             'collection':learner.collection_settings,
             'runtime':runtime(), 'experiment':learner.experiment.to_dict(),
             'optimizer':learner.optimizer.state_dict(), 'action_rng':learner.action_generator.get_state(),
             'update_rng':learner.update_generator.get_state(), 'episode_cursor':learner.episode_cursor,
             'decisions':learner.decisions, 'iterations':learner.iterations, 'updates':learner.updates}
    digest = _save_inference(path, learner.model, learner.experiment.training.reward,
        learner.updates, learner.experiment.to_dict(), algorithm='ppo', resume_digest=_state_digest(state))
    state['bundle_sha256'] = digest
    publish(resume_path, _tensor_bytes(state), private=True)
    return digest


def _state_digest(state):
    """Bind private counters/RNG/optimizer without placing them in the bundle."""
    digest = hashlib.sha256()
    def token(value):
        digest.update(len(value).to_bytes(8, 'big')+value)
    def visit(value):
        token(type(value).__name__.encode())
        if type(value) is torch.Tensor:
            token(str(value.dtype).encode())
            token(str(tuple(value.shape)).encode())
            token(value.detach().cpu().contiguous().numpy().tobytes())
        elif type(value) is dict:
            for key in sorted(value, key=lambda k:(type(k).__name__, str(k))):
                visit(key)
                visit(value[key])
        elif type(value) in (tuple, list):
            for child in value:
                visit(child)
        elif type(value) in (str, bool, int, float, type(None)):
            token(json.dumps(value, allow_nan=False).encode())
        else:
            raise ValueError('Unsupported private checkpoint state type')
        token(b'end')
    visit(state)
    return digest.hexdigest()


def restore_ppo(bundle_path, resume_path, *, experiment=None, env_factory=None, workers=None):
    from .ppo import PPOLearner, UPDATE_POLICY
    from .parallel import collection_settings
    from .ppo_config import PPOExperiment
    path = Path(resume_path)
    if (not path.name.endswith('.resume.pt') or path.stat().st_mode & 0o077 or
            path.parent.stat().st_mode & 0o077 or path.stat().st_size > 128*1024*1024):
        raise ValueError('Expected a published owner-only bounded resume file')
    policy = load_policy(bundle_path)
    if policy.algorithm != 'ppo' or policy.manifest['implementation'] != asdict(implementation()):
        raise ValueError('PPO resume requires its unchanged implementation sources')
    settings = PPOExperiment.from_dict(policy.manifest['learner_config'])
    if experiment is not None and experiment != settings:
        raise ValueError('PPO resume cannot change its experiment')
    state = torch.load(path, map_location='cpu', weights_only=True)
    keys = {'schema', 'bundle_sha256', 'boundary', 'runtime', 'experiment', 'optimizer', 'action_rng',
            'update_rng', 'episode_cursor', 'decisions', 'iterations', 'updates'}
    if type(state) is dict and state.get('schema') in (PPO_RESUME_SCHEMA, 'sts_ppo_resume_v2'):
        keys.add('collection')
    skipped = state.get('skipped_iterations', 0) if type(state) is dict else 0
    if type(state) is dict and state.get('schema') == PPO_RESUME_SCHEMA:
        keys.update(('update_policy', 'skipped_iterations'))
        if state.get('update_policy') != UPDATE_POLICY:
            raise ValueError('Unsupported PPO update policy')
    if (type(state) is not dict or set(state) != keys or state['schema'] not in (PPO_RESUME_SCHEMA, 'sts_ppo_resume_v2', 'sts_ppo_resume_v1') or
            state['bundle_sha256'] != policy.identity.split(':')[-1] or state['boundary'] != 'closed_rollout_update' or
            state['runtime'] != runtime() or state['experiment'] != settings.to_dict() or
            any(type(state[k]) is not int or state[k] < 0 for k in ('episode_cursor', 'decisions', 'iterations', 'updates')) or
            state['updates'] != policy.manifest['updates'] or state['iterations'] > state['decisions'] or
            type(skipped) is not int or not 0 <= skipped <= state['iterations'] or
            not state['iterations']-skipped <= state['updates'] <= (state['iterations']-skipped)*settings.ppo.epochs*
                ((settings.ppo.rollout_steps+settings.ppo.batch_size-1)//settings.ppo.batch_size) or
            (state['iterations'] == 0) != (state['decisions'] == 0)):
        raise ValueError('Incompatible PPO resume state')
    if _state_digest({k:v for k,v in state.items() if k != 'bundle_sha256'}) != policy.manifest['resume_state_sha256']:
        raise ValueError('Private PPO state does not match the inference checkpoint')
    collection = state.get('collection', collection_settings(1))
    if (type(collection) is not dict or collection_settings(collection.get('workers')) != collection or
            workers is not None and collection_settings(workers) != collection):
        raise ValueError('Exact PPO resume cannot change its worker allocation')
    learner = PPOLearner(policy.model, settings, cursor=state['episode_cursor'], env_factory=env_factory,
                         workers=collection['workers'])
    restore_adam(learner, state['optimizer'], state['updates'])
    try:
        learner.action_generator.set_state(state['action_rng'])
        learner.update_generator.set_state(state['update_rng'])
    except (TypeError, RuntimeError) as error:
        raise ValueError('Invalid learner RNG state') from error
    learner.decisions, learner.iterations, learner.updates = state['decisions'], state['iterations'], state['updates']
    learner.skipped_iterations = skipped
    return learner
