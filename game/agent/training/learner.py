"""Bounded behaviour cloning of public demonstrations, with optional value labels."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import time

import torch
from game.agent.action_policy import ALL_LEGAL, validate_policy

from .dataset import load_training_dataset
from .features import FeatureEncoder, Vocabulary
from .combat_features import GRAPH, COMBAT_REPRESENTATIONS, feature_identity
from .model import collate, policy_statistics


@dataclass(frozen=True, slots=True)
class Example:
    state: object
    action: int
    value_target: float | None


@dataclass(frozen=True, slots=True)
class Corpus:
    examples: tuple[Example, ...]
    vocabulary: Vocabulary
    reward_spec: object
    identity: str
    split: str
    episodes: int
    encoding_seconds: float
    action_policy: str = ALL_LEGAL

    @property
    def nbytes(self):
        return sum(e.state.nbytes for e in self.examples)


def load_corpus(pairs, *, split, vocabulary=None, reward_spec=None, action_policy=ALL_LEGAL, representation=GRAPH,
                include_catalog=True):
    validate_policy(action_policy)
    pairs = tuple(pairs)
    if vocabulary is None:
        if split != 'train':
            raise ValueError('Validation/test data require the frozen training vocabulary')
        decisions = (step.transition.observation for episode in load_training_dataset(
            pairs, split=split, reward_spec=reward_spec) for step in episode.transitions)
        vocabulary = Vocabulary.fit(decisions, split='train', include_catalog=include_catalog)
    encoder = FeatureEncoder(vocabulary, action_policy=action_policy, representation=representation)
    examples, bindings, objective, seconds = [], [], None, 0.0
    for episode in load_training_dataset(pairs, split=split, reward_spec=reward_spec):
        objective = episode.reward_spec
        # A cutoff is not a terminal Monte Carlo value label. PPO will introduce
        # explicit value bootstrapping in milestone 4, rather than invent it here.
        returns, total = [], 0.0
        discount = objective.discount if objective.discount is not None else 1.0
        for step in reversed(episode.transitions):
            total = step.reward + discount * total
            if not math.isfinite(total):
                raise ValueError('Nonfinite demonstration return')
            returns.append(total if episode.ending.terminated else None)
        before = time.perf_counter()
        for step, value in zip(episode.transitions, reversed(returns)):
            state = encoder.encode(step.transition.observation)
            action = state.graph.candidate_refs.index(step.transition.action.ref)
            if not state.policy_mask[action]:
                raise ValueError('Demonstration action is excluded by the declared action policy')
            examples.append(Example(state, action, value))
        seconds += time.perf_counter() - before
        bindings.append((episode.trajectory.sha256, episode.reward_spec.identity,
                         [(asdict(s.components), s.terminated, s.truncated, asdict(s.combat))
                          for s in episode.transitions]))
    if not examples:
        raise ValueError('Imitation corpus has no reconciled decisions')
    payload = [feature_identity(vocabulary, representation), bindings] + ([action_policy] if action_policy != ALL_LEGAL else [])
    data = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    identity = 'sts_imitation_corpus_v1:' + hashlib.sha256(data.encode()).hexdigest()
    return Corpus(tuple(examples), vocabulary, objective, identity, split, len(bindings), seconds, action_policy)


@dataclass(frozen=True, slots=True)
class LearnerConfig:
    batch_size: int = 8
    learning_rate: float = 0.003
    value_weight: float = 0.25
    gradient_clip: float = 1.0

    def __post_init__(self):
        if type(self.batch_size) is not int or not 1 <= self.batch_size <= 256:
            raise ValueError('Batch size must be between 1 and 256')
        for name in ('learning_rate', 'value_weight', 'gradient_clip'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Learner settings must be finite nonnegative numbers')
        if self.learning_rate == 0 or self.gradient_clip == 0:
            raise ValueError('Learning rate and gradient clip must be positive')


class ImitationLearner:
    """Single CPU owner. Checkpoints are only taken between complete updates.

    There is no in-flight game/collector in this offline learner. The corpus is
    made of complete recorded episodes; interrupted collection must start afresh.
    """
    def __init__(self, model, corpus, config=LearnerConfig(), *, seed=0):
        if corpus.split != 'train' or corpus.vocabulary != model.vocabulary:
            raise ValueError('Learner requires a compatible training corpus')
        if (corpus.action_policy != model.action_policy or
                any(e.state.action_policy != model.action_policy for e in corpus.examples)):
            raise ValueError('Imitation requires one matching policy-action version')
        if any((e.state.combat is not None) != (model.architecture.schema in COMBAT_REPRESENTATIONS) for e in corpus.examples):
            raise ValueError('Imitation feature representation differs from model')
        from .action_features import mode
        if any(e.state.preview_mode != mode(model.architecture.schema) for e in corpus.examples):
            raise ValueError('Imitation action preview representation differs from model')
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Learner seed must be a nonnegative int64')
        if next(model.parameters()).device.type != 'cpu':
            raise ValueError('Milestone 3 supports deterministic CPU learning')
        self.model, self.corpus, self.config = model, corpus, config
        model.requires_grad_(True)
        self.optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate, foreach=False)
        self.generator = torch.Generator(device='cpu').manual_seed(seed)
        self.order = torch.randperm(len(corpus.examples), generator=self.generator)
        self.cursor = self.updates = 0
        self.failed = False

    def step(self):
        if self.failed:
            raise RuntimeError('Learner failed; reload a complete checkpoint')
        before = time.perf_counter()
        try:
            if self.cursor == len(self.order):
                self.order = torch.randperm(len(self.corpus.examples), generator=self.generator)
                self.cursor = 0
            indexes = self.order[self.cursor:self.cursor + self.config.batch_size].tolist()
            examples = [self.corpus.examples[i] for i in indexes]
            batch = collate([e.state for e in examples], vocabulary=self.corpus.vocabulary)
            self.model.train()
            logits, values = self.model(batch)
            logp, entropy = policy_statistics(logits, batch['mask'], torch.tensor([e.action for e in examples]))
            available = torch.tensor([e.value_target is not None for e in examples])
            targets = torch.tensor([e.value_target if e.value_target is not None else 0.0 for e in examples])
            value_loss = (values[available] - targets[available]).square().mean() if available.any() else values.sum() * 0
            imitation_loss = -logp.mean()
            loss = imitation_loss + self.config.value_weight * value_loss
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite learner loss')
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip,
                                                 error_if_nonfinite=True)
            self.optimizer.step()
            if any(not torch.isfinite(p).all() for p in self.model.parameters()):
                raise ValueError('Nonfinite learner parameters')
            self.cursor += len(indexes)
            self.updates += 1
            return {'update': self.updates, 'loss': loss.item(), 'imitation_loss': imitation_loss.item(),
                    'value_loss': value_loss.item(), 'entropy': entropy.mean().item(),
                    'gradient_norm': norm.item(), 'samples': len(indexes),
                    'batch_tensor_bytes': sum(t.numel()*t.element_size() for t in batch.values()),
                    'seconds': time.perf_counter() - before}
        except BaseException:
            self.failed = True
            raise


def evaluate_imitation(model, corpus, *, batch_size=16):
    if corpus.vocabulary != model.vocabulary:
        raise ValueError('Incompatible evaluation vocabulary')
    if corpus.action_policy != model.action_policy:
        raise ValueError('Evaluation policy-action version differs from corpus')
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError('Expected a positive evaluation batch size')
    correct = count = 0
    loss = value_error = entropy_total = 0.0
    value_count = 0
    started = time.perf_counter()
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(corpus.examples), batch_size):
            examples = corpus.examples[start:start+batch_size]
            batch = collate([e.state for e in examples], vocabulary=corpus.vocabulary)
            logits, values = model(batch)
            targets = torch.tensor([e.action for e in examples])
            logp, entropy = policy_statistics(logits, batch['mask'], targets)
            loss -= logp.sum().item()
            entropy_total += entropy.sum().item()
            correct += (logits.masked_fill(~batch['mask'], -torch.inf).argmax(-1) == targets).sum().item()
            for value, example in zip(values.tolist(), examples):
                if not math.isfinite(value):
                    raise ValueError('Nonfinite value prediction')
                if example.value_target is not None:
                    value_error += (value-example.value_target)**2
                    value_count += 1
            count += len(examples)
    return {'decisions': count, 'imitation_loss': loss/count, 'accuracy': correct/count,
            'entropy': entropy_total/count, 'value_mse': value_error/value_count if value_count else None,
            'value_labels': value_count, 'seconds': time.perf_counter()-started}
