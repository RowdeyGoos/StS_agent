"""Minimal Slay-the-Spire-style combat simulator package."""

from .actions import CombatAction
from .baselines import (
    EvaluationSnapshot,
    EvaluationStats,
    QLearningAgent,
    TrainingResult,
    choose_heuristic_action,
    choose_random_action,
    evaluate_policy,
    train_q_learning,
)
from .card import BashCard, Card, DefendCard, SlimedCard, StrikeCard, create_starter_deck
from .core import CombatEnv
from .dqn import (
    DQNAgent,
    DQNTrainingResult,
    DoubleDQNAgent,
    ReplayBuffer,
    ReplayTransition,
    train_double_dqn,
    train_dqn,
)
from .encoding import ObservationEncoder
from .enemy import (
    Enemy,
    FuzzyWurmCrawler,
    Intent,
    LeafSlimeMedium,
    LeafSlimeSmall,
    Nibbit,
    ShrinkerBeetle,
    SimpleEnemy,
    TwigSlimeMedium,
    TwigSlimeSmall,
    build_overgrowth_easy_encounter,
    sample_overgrowth_first_three_encounter_builders,
)
from .gym_env import GymCombatEnv
from .player import Player
from .status import (
    SHRINK,
    STATUS_STACK_SCALE,
    SUPPORTED_STATUS_NAMES,
    StatusCollection,
    VULNERABLE,
)
from .trajectory import EpisodeSummary, TransitionRecord

__all__ = [
    "BashCard",
    "Card",
    "CombatAction",
    "CombatEnv",
    "DefendCard",
    "DQNAgent",
    "DQNTrainingResult",
    "DoubleDQNAgent",
    "Enemy",
    "EvaluationSnapshot",
    "EvaluationStats",
    "EpisodeSummary",
    "FuzzyWurmCrawler",
    "GymCombatEnv",
    "Intent",
    "LeafSlimeMedium",
    "LeafSlimeSmall",
    "Nibbit",
    "ObservationEncoder",
    "Player",
    "QLearningAgent",
    "ReplayBuffer",
    "ReplayTransition",
    "ShrinkerBeetle",
    "SimpleEnemy",
    "SlimedCard",
    "SHRINK",
    "StatusCollection",
    "STATUS_STACK_SCALE",
    "StrikeCard",
    "SUPPORTED_STATUS_NAMES",
    "TrainingResult",
    "TransitionRecord",
    "TwigSlimeMedium",
    "TwigSlimeSmall",
    "VULNERABLE",
    "build_overgrowth_easy_encounter",
    "choose_heuristic_action",
    "choose_random_action",
    "create_starter_deck",
    "evaluate_policy",
    "sample_overgrowth_first_three_encounter_builders",
    "train_double_dqn",
    "train_dqn",
    "train_q_learning",
]
