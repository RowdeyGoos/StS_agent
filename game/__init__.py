"""Stable symbol-level public API for the combat simulator package.

Imports stay lazy so lightweight commands can display help without importing
optional RL dependencies.  Resolved values retain their canonical providers.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


__all__ = [
    "BashCard", "BodySlamCard", "BruteForceProgress", "BruteForceResult", "Card",
    "CardSpec", "CombatAction", "CombatEnv", "CombatEnvFactory", "DefendCard",
    "DQNAgent", "DQNTrainingResult", "DoubleDQNAgent", "DuelingDoubleDQNAgent",
    "Enemy", "EncounterEvaluationStats", "EvaluationSnapshot", "EvaluationStats",
    "EpisodeTrace", "EpisodeSummary", "FuzzyWurmCrawler", "GymCombatEnv",
    "InformationAwareActionEvaluation", "InformationAwareDecisionAnalysis",
    "InformationAwarePolicyAnalysis", "Intent", "IronWaveCard", "LeafSlimeMedium",
    "LeafSlimeSmall", "Mawler", "Nibbit", "ObservationEncoder",
    "OracleActionEvaluation", "OracleDecisionAnalysis", "OraclePolicyAnalysis",
    "OracleStep", "Player", "PPOAgent", "PPOTrainingResult", "PommelStrikeCard",
    "QLearningAgent", "ReplayBuffer", "ReplayTransition", "ShrinkerBeetle",
    "ShrugItOffCard", "SimpleEnemy", "SlimedCard", "SHRINK", "StepTrace",
    "StatusCollection", "STATUS_STACK_SCALE", "StrikeCard", "SUPPORTED_ENCOUNTERS",
    "SUPPORTED_DECKS", "SUPPORTED_FIXED_ENCOUNTERS", "SUPPORTED_TRAINING_ENCOUNTER_SETS",
    "SUPPORTED_STATUS_NAMES", "TraceAnalysisReport", "TraceFinding", "TrainingResult",
    "TransitionRecord", "TwigSlimeMedium", "TwigSlimeSmall", "VULNERABLE",
    "build_overgrowth_easy_encounter", "build_overgrowth_hard_v1_encounter",
    "build_overgrowth_mawler_encounter", "build_overgrowth_nibbits_encounter",
    "build_overgrowth_shrinker_fuzzy_encounter", "build_overgrowth_slimes_encounter",
    "brute_force_combat", "choose_heuristic_action", "choose_random_action",
    "create_ironclad_sequencing_deck", "create_starter_deck", "evaluate_policy",
    "get_card_spec", "load_agent", "load_episode_trace",
    "sample_overgrowth_first_three_encounter_builders", "sample_hidden_combat_states",
    "resolve_deck_factory", "save_agent", "save_episode_trace", "analyze_episode_trace",
    "analyze_episode_trace_with_oracle", "analyze_episode_trace_with_uncertainty",
    "analyze_information_aware_decision", "analyze_oracle_decision", "trace_policy_episode",
    "train_double_dqn", "train_dqn", "train_dueling_double_dqn", "train_masked_ppo",
    "train_q_learning",
]

_SOURCE_GROUPS = {
    ".agents.agent_io": ("load_agent", "save_agent"),
    ".agents.baselines": (
        "EncounterEvaluationStats", "EvaluationSnapshot", "EvaluationStats", "QLearningAgent",
        "TrainingResult", "choose_heuristic_action", "choose_random_action", "evaluate_policy",
        "train_q_learning",
    ),
    ".agents.dqn": (
        "DQNAgent", "DQNTrainingResult", "DoubleDQNAgent", "DuelingDoubleDQNAgent",
        "ReplayBuffer", "ReplayTransition", "train_double_dqn", "train_dqn", "train_dueling_double_dqn",
    ),
    ".agents.ppo": ("PPOAgent", "PPOTrainingResult", "train_masked_ppo"),
    ".analysis.bruteforce": ("BruteForceProgress", "BruteForceResult", "OracleStep", "brute_force_combat"),
    ".analysis.oracle": (
        "OracleActionEvaluation", "OracleDecisionAnalysis", "OraclePolicyAnalysis",
        "analyze_episode_trace_with_oracle", "analyze_oracle_decision",
    ),
    ".analysis.trace": ("TraceAnalysisReport", "TraceFinding", "analyze_episode_trace"),
    ".analysis.uncertainty": (
        "InformationAwareActionEvaluation", "InformationAwareDecisionAnalysis",
        "InformationAwarePolicyAnalysis", "analyze_episode_trace_with_uncertainty",
        "analyze_information_aware_decision", "sample_hidden_combat_states",
    ),
    ".analysis.watch": ("EpisodeTrace", "StepTrace", "load_episode_trace", "save_episode_trace", "trace_policy_episode"),
    ".simulation.actions": ("CombatAction",),
    ".simulation.card": (
        "BashCard", "BodySlamCard", "Card", "CardSpec", "DefendCard", "IronWaveCard",
        "PommelStrikeCard", "ShrugItOffCard", "SlimedCard", "StrikeCard",
        "create_ironclad_sequencing_deck", "create_starter_deck", "get_card_spec",
    ),
    ".simulation.core": ("CombatEnv",),
    ".simulation.deck_presets": ("SUPPORTED_DECKS", "resolve_deck_factory"),
    ".simulation.encoding": ("ObservationEncoder",),
    ".simulation.env_factory": (
        "CombatEnvFactory", "SUPPORTED_ENCOUNTERS", "SUPPORTED_FIXED_ENCOUNTERS",
        "SUPPORTED_TRAINING_ENCOUNTER_SETS",
    ),
    ".simulation.enemy": (
        "Enemy", "FuzzyWurmCrawler", "Intent", "LeafSlimeMedium", "LeafSlimeSmall", "Mawler",
        "Nibbit", "ShrinkerBeetle", "SimpleEnemy", "TwigSlimeMedium", "TwigSlimeSmall",
        "build_overgrowth_easy_encounter", "build_overgrowth_hard_v1_encounter",
        "build_overgrowth_mawler_encounter", "build_overgrowth_nibbits_encounter",
        "build_overgrowth_shrinker_fuzzy_encounter", "build_overgrowth_slimes_encounter",
        "sample_overgrowth_first_three_encounter_builders",
    ),
    ".simulation.gym_env": ("GymCombatEnv",),
    ".simulation.player": ("Player",),
    ".simulation.status": ("SHRINK", "STATUS_STACK_SCALE", "SUPPORTED_STATUS_NAMES", "StatusCollection", "VULNERABLE"),
    ".simulation.trajectory": ("EpisodeSummary", "TransitionRecord"),
}
_PUBLIC_SOURCES = {
    name: source for source, names in _SOURCE_GROUPS.items() for name in names
}
if set(__all__) != set(_PUBLIC_SOURCES):  # pragma: no cover - import-time invariant
    raise RuntimeError("Public API names and canonical sources are out of sync.")


def __getattr__(name: str) -> Any:
    """Resolve and cache one public symbol from its canonical module."""

    try:
        source = _PUBLIC_SOURCES[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(source, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose unresolved public names to ordinary package introspection."""

    return sorted(set(globals()) | set(__all__))
