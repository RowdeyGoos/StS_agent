"""Training examples with task flags and explicitly compatible objectives."""
from dataclasses import dataclass

from game.agent.dataset import EncodedTransition
from game.agent.recording import SPLITS, load_trajectory
from .records import TrainingRecordError, _read, _validate
from .rewards import RewardSpec


@dataclass(frozen=True, slots=True)
class TrainingExample(EncodedTransition):
    reward_spec_id: str


def load_training_dataset(pairs, *, split, expected=None, reward_spec=None):
    """Load explicit (trajectory, sidecar) pairs from a single split.

    Preflight compact objectives before yielding any episodes. Different recorded
    objectives require an explicit conversion to one RewardSpec. Only one episode
    of full observations is loaded at a time; audits are never consulted.
    """
    if split not in SPLITS:
        raise TrainingRecordError('An explicit train/validation/test split is required')
    if reward_spec is not None and (type(reward_spec) is not RewardSpec or reward_spec.task != 'combat'):
        raise TrainingRecordError('Expected an explicit RewardSpec conversion')
    pending, identities = [], set()
    for trajectory_path, sidecar_path in pairs:
        value, spec = _read(sidecar_path)
        pending.append((trajectory_path, value, spec))
        identities.add(spec.identity)
    if reward_spec is None and len(identities) > 1:
        raise TrainingRecordError('Mixed reward specifications require explicit conversion')
    for path, value, spec in pending:
        trajectory = load_trajectory(path, split=split, expected=expected)
        yield _validate(value, spec, trajectory, reward_spec)


def training_examples(pairs, *, split, encoder, expected=None, reward_spec=None):
    """Encode unchanged public observations with sidecar rewards/task flags.

    Specification identity labels each sample but is never a policy input. True
    task termination suppresses bootstrapping even when the run was truncated.
    """
    for episode in load_training_dataset(pairs, split=split, expected=expected, reward_spec=reward_spec):
        for step in episode.transitions:
            transition = step.transition
            encoded = encoder.encode(transition.observation)
            successor = encoder.encode(transition.successor)
            yield TrainingExample(
                encoder.profile.identity, encoded.observation,
                encoded.candidate_refs.index(transition.action.ref), successor.observation,
                step.reward, step.terminated, step.truncated, episode.reward_spec.identity)
