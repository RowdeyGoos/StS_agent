"""Trace-analysis helpers for finding common tactical mistakes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .action_features import infer_legal_actions_from_observation, summarize_action
from .render import describe_action
from .watch import EpisodeTrace, StepTrace, load_episode_trace


@dataclass(frozen=True, slots=True)
class TraceFinding:
    """One high-confidence tactical issue found in a traced combat."""

    step_index: int
    turn: int
    category: str
    severity: float
    chosen_action: tuple[object, ...]
    recommended_action: tuple[object, ...] | None
    description: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the finding."""
        return {
            "step_index": self.step_index,
            "turn": self.turn,
            "category": self.category,
            "severity": self.severity,
            "chosen_action": list(self.chosen_action),
            "recommended_action": (
                None
                if self.recommended_action is None
                else list(self.recommended_action)
            ),
            "description": self.description,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class TraceAnalysisReport:
    """Aggregate result of analyzing one traced combat."""

    policy_name: str
    seed: int | None
    total_steps: int
    category_counts: dict[str, int]
    findings: tuple[TraceFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the report."""
        return {
            "policy_name": self.policy_name,
            "seed": self.seed,
            "total_steps": self.total_steps,
            "category_counts": dict(self.category_counts),
            "findings": [finding.as_dict() for finding in self.findings],
        }


def analyze_trace_file(path: str | Path) -> TraceAnalysisReport:
    """Load and analyze one saved episode trace file."""
    return analyze_episode_trace(load_episode_trace(path))


def analyze_episode_trace(trace: EpisodeTrace) -> TraceAnalysisReport:
    """Analyze one traced episode for common tactical mistakes."""
    findings: list[TraceFinding] = []
    category_counts: Counter[str] = Counter()

    for step in trace.steps:
        step_findings = _analyze_step(step)
        findings.extend(step_findings)
        category_counts.update(finding.category for finding in step_findings)

    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda finding: (-finding.severity, finding.step_index, finding.category),
        )
    )
    return TraceAnalysisReport(
        policy_name=trace.policy_name,
        seed=trace.seed,
        total_steps=len(trace.steps),
        category_counts=dict(sorted(category_counts.items())),
        findings=ordered_findings,
    )


def format_finding(finding: TraceFinding, trace: EpisodeTrace | None = None) -> str:
    """Render one finding as a compact human-readable line."""
    chosen_description = _render_action(
        finding.chosen_action,
        trace.steps[finding.step_index].observation if trace is not None else None,
    )
    recommended_description = None
    if finding.recommended_action is not None:
        recommended_description = _render_action(
            finding.recommended_action,
            trace.steps[finding.step_index].observation if trace is not None else None,
        )

    fragments = [
        f"step={finding.step_index}",
        f"turn={finding.turn}",
        f"category={finding.category}",
        f"severity={finding.severity:.2f}",
        finding.description,
        f"chosen={chosen_description}",
    ]
    if recommended_description is not None:
        fragments.append(f"recommended={recommended_description}")
    return " | ".join(fragments)


def _analyze_step(step: StepTrace) -> list[TraceFinding]:
    legal_actions = step.legal_actions or infer_legal_actions_from_observation(step.observation)
    action_summaries = {
        action: summarize_action(step.observation, action)
        for action in legal_actions
    }
    chosen_summary = action_summaries.get(step.action)
    if chosen_summary is None:
        chosen_summary = summarize_action(step.observation, step.action)
        action_summaries = dict(action_summaries)
        action_summaries[step.action] = chosen_summary

    alternative_summaries = [
        summary
        for action, summary in action_summaries.items()
        if action != step.action
    ]
    findings: list[TraceFinding] = []

    lethal_alternative = _best_summary(
        summary
        for summary in alternative_summaries
        if summary.wins_combat
    )
    if lethal_alternative is not None and not chosen_summary.wins_combat:
        findings.append(
            _make_finding(
                step=step,
                category="missed_lethal",
                severity=1.0,
                chosen_summary=chosen_summary,
                recommended_summary=lethal_alternative,
                description="Could have ended the combat immediately.",
            )
        )

    if (
        chosen_summary.projected_incoming_hp_loss_before > 0
        and not chosen_summary.wins_combat
    ):
        best_defensive = _best_summary(
            alternative_summaries,
            key=_defensive_priority_tuple,
        )
        if best_defensive is not None:
            reduction_gap = (
                best_defensive.incoming_hp_loss_reduction
                - chosen_summary.incoming_hp_loss_reduction
            )
            if reduction_gap > 0 and (
                chosen_summary.is_dead_card
                or chosen_summary.action[0] == "end_turn"
                or reduction_gap >= 3
            ):
                findings.append(
                    _make_finding(
                        step=step,
                        category="ignored_damage_prevention",
                        severity=float(reduction_gap),
                        chosen_summary=chosen_summary,
                        recommended_summary=best_defensive,
                        description=(
                            "A legal alternative would have reduced more incoming damage "
                            "before the enemy turn."
                        ),
                    )
                )

    if chosen_summary.is_dead_card:
        productive_alternative = _best_summary(
            summary
            for summary in alternative_summaries
            if _priority_tuple(summary) > _priority_tuple(chosen_summary)
        )
        if productive_alternative is not None:
            findings.append(
                _make_finding(
                    step=step,
                    category="wasted_dead_card",
                    severity=0.75,
                    chosen_summary=chosen_summary,
                    recommended_summary=productive_alternative,
                    description="Played a dead card when a more useful action was available.",
                )
            )

    if chosen_summary.uses_target and chosen_summary.card_name is not None:
        better_target = _best_summary(
            summary
            for summary in alternative_summaries
            if summary.card_name == chosen_summary.card_name
        )
        if better_target is not None and _priority_tuple(better_target) > _priority_tuple(
            chosen_summary
        ):
            findings.append(
                _make_finding(
                    step=step,
                    category="suboptimal_target",
                    severity=0.5,
                    chosen_summary=chosen_summary,
                    recommended_summary=better_target,
                    description="The same card had a better target this turn.",
                )
            )

    if chosen_summary.action[0] == "end_turn":
        best_non_end_turn = _best_summary(
            summary
            for summary in alternative_summaries
            if summary.action[0] != "end_turn"
        )
        if best_non_end_turn is not None and _priority_tuple(best_non_end_turn) > _priority_tuple(
            chosen_summary
        ):
            findings.append(
                _make_finding(
                    step=step,
                    category="premature_end_turn",
                    severity=0.5,
                    chosen_summary=chosen_summary,
                    recommended_summary=best_non_end_turn,
                    description="Ended the turn while a higher-value play was still legal.",
                )
            )

    return findings


def _make_finding(
    *,
    step: StepTrace,
    category: str,
    severity: float,
    chosen_summary: Any,
    recommended_summary: Any,
    description: str,
) -> TraceFinding:
    details: dict[str, Any] = {
        "chosen_incoming_hp_loss_before": chosen_summary.projected_incoming_hp_loss_before,
        "chosen_incoming_hp_loss_after": chosen_summary.projected_incoming_hp_loss_after,
        "recommended_incoming_hp_loss_after": (
            recommended_summary.projected_incoming_hp_loss_after
            if recommended_summary is not None
            else None
        ),
        "chosen_card": chosen_summary.card_name,
        "recommended_card": (
            None if recommended_summary is None else recommended_summary.card_name
        ),
    }
    if step.legal_action_scores is not None and recommended_summary is not None:
        details["selected_action_score"] = step.selected_action_score

    return TraceFinding(
        step_index=step.step_index,
        turn=step.turn,
        category=category,
        severity=severity,
        chosen_action=chosen_summary.action,
        recommended_action=(
            None if recommended_summary is None else recommended_summary.action
        ),
        description=description,
        details=details,
    )


def _best_summary(
    summaries: Any,
    *,
    key: Any = None,
) -> Any | None:
    materialized = list(summaries)
    if not materialized:
        return None
    return max(materialized, key=_priority_tuple if key is None else key)


def _priority_tuple(summary: Any) -> tuple[float, ...]:
    return (
        1.0 if summary.wins_combat else 0.0,
        1.0 if summary.kills_target else 0.0,
        float(summary.incoming_hp_loss_reduction),
        float(summary.damage_to_target),
        float(summary.block_gain),
        float(summary.applies_status_stacks),
        0.0 if summary.is_dead_card else 1.0,
        0.0 if summary.action[0] == "end_turn" else 1.0,
    )


def _defensive_priority_tuple(summary: Any) -> tuple[float, ...]:
    return (
        float(summary.incoming_hp_loss_reduction),
        1.0 if summary.wins_combat else 0.0,
        1.0 if summary.kills_target else 0.0,
        float(summary.block_gain),
        float(summary.damage_to_target),
        float(summary.applies_status_stacks),
        0.0 if summary.is_dead_card else 1.0,
    )


def _render_action(
    action: tuple[object, ...],
    observation: dict[str, Any] | None,
) -> str:
    if observation is None:
        return str(action)
    return describe_action(action, observation)
