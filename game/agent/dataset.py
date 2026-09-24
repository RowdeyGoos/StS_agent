"""Split-checked public datasets and optional, lossless training examples."""
from dataclasses import dataclass

from game.agent import contracts as c
from game.agent.recording import SPLITS, TrajectoryError, load_trajectory


@dataclass(frozen=True, slots=True)
class EncodedTransition:
    encoding: str
    observation: dict
    action: int
    successor: dict
    reward: float
    terminated: bool
    truncated: bool


def load_dataset(paths, *, split, expected=None):
    """Yield validated public episodes from one explicitly named dataset split."""
    if split not in SPLITS:
        raise TrajectoryError('An explicit train/validation/test split is required')
    for path in paths:
        yield load_trajectory(path, split=split, expected=expected)


def training_examples(paths, *, split, encoder, expected=None):
    """Encode original candidate identities into exact model action slots.

    Metadata and audit paths never become model inputs. A cutoff retains its
    final ready observation/mask for bootstrapping; true terminals encode the
    actual outcome. Capacity errors propagate without dropping any sample.
    """
    for trajectory in load_dataset(paths, split=split, expected=expected):
        for index, transition in enumerate(trajectory.transitions):
            encoded = encoder.encode(transition.observation)
            successor = encoder.encode(transition.successor)
            last = index == len(trajectory.transitions) - 1
            terminal = isinstance(transition.successor, c.RunOutcome)
            yield EncodedTransition(
                encoder.profile.identity, encoded.observation,
                encoded.candidate_refs.index(transition.action.ref), successor.observation,
                float(transition.reward), terminal and transition.successor.kind != 'truncated',
                last and trajectory.outcome.kind == 'truncated')
