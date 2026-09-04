"""Trusted, public-only actor examples from finalized headless experiments.

This consumer deliberately receives a trusted experiment-manifest digest and
uses the established experiment loader before reading a trajectory's *policy*
stream.  Hindsight-target and synthetic-audit streams are authenticated by the
trusted loader, but are never decoded or represented by actor examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from game.contracts.headless_v0 import (
    BackendManifest,
    ComponentEvidence,
    DecisionStatus,
    EvidenceLabel,
    PolicyView,
    canonical_json_bytes,
)
from game.data.headless_trajectory import (
    FinalizedTrajectory,
    PolicyReplayRecord,
    TrajectoryValidationError,
    decode_policy_replay,
    policy_view_for,
)
from game.training.headless_reporting import (
    ExperimentIntegrityError,
    ExperimentValidationError,
    HeadlessExperimentConfig,
    LoadedHeadlessExperiment,
    load_headless_experiment,
)


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ActorDatasetValidationError(ValueError):
    """Raised when trusted actor-example inputs violate this dataset contract."""


class ActorSplit(str, Enum):
    """The two declared, non-overlapping actor-example panels."""

    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


@dataclass(frozen=True, slots=True)
class TrustedExperimentSource:
    """One finalized experiment root plus its externally retained digest."""

    root: Path
    expected_manifest_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError("root must be a pathlib.Path.")
        if (
            not isinstance(self.expected_manifest_sha256, str)
            or _SHA256.fullmatch(self.expected_manifest_sha256) is None
        ):
            raise ActorDatasetValidationError(
                "expected_manifest_sha256 must be a lowercase SHA-256 digest."
            )


@dataclass(frozen=True, slots=True)
class ActorExampleProvenance:
    """The only retained identity information for one actor example."""

    experiment_manifest_sha256: str
    repetition_index: int
    trajectory_id: str
    trajectory_manifest_sha256: str
    policy_record_ordinal: int

    def __post_init__(self) -> None:
        for name in ("experiment_manifest_sha256", "trajectory_manifest_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ActorDatasetValidationError(f"{name} must be a lowercase SHA-256 digest.")
        for name in ("repetition_index", "policy_record_ordinal"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ActorDatasetValidationError(f"{name} must be a nonnegative integer.")
        if not isinstance(self.trajectory_id, str) or not self.trajectory_id:
            raise ActorDatasetValidationError("trajectory_id must be nonempty text.")


@dataclass(frozen=True, slots=True)
class ActorExample:
    """A public policy boundary, its chosen advertised ID, and trusted provenance."""

    policy_view: PolicyView
    chosen_candidate_id: str
    provenance: ActorExampleProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.policy_view, PolicyView):
            raise TypeError("policy_view must be a PolicyView.")
        if self.policy_view.status is not DecisionStatus.ACTIONABLE:
            raise ActorDatasetValidationError("Actor examples must be actionable.")
        if not isinstance(self.chosen_candidate_id, str):
            raise TypeError("chosen_candidate_id must be text.")
        if self.chosen_candidate_id not in {
            candidate.candidate_id for candidate in self.policy_view.candidates
        }:
            raise ActorDatasetValidationError(
                "chosen_candidate_id must be one of the advertised candidates."
            )
        if not isinstance(self.provenance, ActorExampleProvenance):
            raise TypeError("provenance must be ActorExampleProvenance.")


@dataclass(frozen=True, slots=True)
class ActorSkipCounts:
    """Exact policy-record exclusions, partitioned by the frozen eligibility rule."""

    non_actionable_records: int = 0
    actionable_without_choice_records: int = 0

    def __post_init__(self) -> None:
        for name in ("non_actionable_records", "actionable_without_choice_records"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ActorDatasetValidationError(f"{name} must be a nonnegative integer.")

    @property
    def total(self) -> int:
        return self.non_actionable_records + self.actionable_without_choice_records


@dataclass(frozen=True, slots=True)
class AdmittedTrajectoryProvenance:
    """Immutable provenance retained for every finalized trajectory admitted to a panel."""

    experiment_manifest_sha256: str
    repetition_index: int
    trajectory_id: str
    trajectory_manifest_sha256: str
    evidence: tuple[ComponentEvidence, ...]

    def __post_init__(self) -> None:
        for name in ("experiment_manifest_sha256", "trajectory_manifest_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ActorDatasetValidationError(f"{name} must be a lowercase SHA-256 digest.")
        if (
            not isinstance(self.repetition_index, int)
            or isinstance(self.repetition_index, bool)
            or self.repetition_index < 0
        ):
            raise ActorDatasetValidationError("repetition_index must be a nonnegative integer.")
        if not isinstance(self.trajectory_id, str) or not self.trajectory_id:
            raise ActorDatasetValidationError("trajectory_id must be nonempty text.")
        evidence = tuple(self.evidence)
        if not evidence or any(not isinstance(item, ComponentEvidence) for item in evidence):
            raise TypeError("evidence must contain ComponentEvidence values.")
        components = tuple(item.component for item in evidence)
        if components != tuple(sorted(set(components))):
            raise ActorDatasetValidationError("evidence components must be unique and sorted.")
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True)
class ActorSplitDataset(Sequence[ActorExample]):
    """Deterministically ordered examples and exclusions for one declared panel."""

    split: ActorSplit
    examples: tuple[ActorExample, ...]
    skip_counts: ActorSkipCounts
    admitted_trajectories: tuple[AdmittedTrajectoryProvenance, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "split", ActorSplit(self.split))
        examples = tuple(self.examples)
        if any(not isinstance(item, ActorExample) for item in examples):
            raise TypeError("examples must contain ActorExample values.")
        identities = tuple(item.provenance for item in examples)
        if len(set(identities)) != len(identities):
            raise ActorDatasetValidationError("Duplicate actor sample identity within a split.")
        if not isinstance(self.skip_counts, ActorSkipCounts):
            raise TypeError("skip_counts must be ActorSkipCounts.")
        trajectories = tuple(self.admitted_trajectories)
        if any(not isinstance(item, AdmittedTrajectoryProvenance) for item in trajectories):
            raise TypeError("admitted_trajectories must contain provenance values.")
        trajectory_identities = tuple(
            (
                item.experiment_manifest_sha256,
                item.repetition_index,
                item.trajectory_id,
                item.trajectory_manifest_sha256,
            )
            for item in trajectories
        )
        if len(set(trajectory_identities)) != len(trajectory_identities):
            raise ActorDatasetValidationError("Duplicate admitted trajectory provenance within a split.")
        object.__setattr__(self, "examples", examples)
        object.__setattr__(self, "admitted_trajectories", trajectories)

    def __getitem__(self, index: int | slice) -> ActorExample | tuple[ActorExample, ...]:
        return self.examples[index]

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self) -> Iterator[ActorExample]:
        return iter(self.examples)


@dataclass(frozen=True, slots=True)
class ActorDataset:
    """The declared development and held-out panels, kept separate by construction."""

    development: ActorSplitDataset
    held_out: ActorSplitDataset

    def __post_init__(self) -> None:
        if self.development.split is not ActorSplit.DEVELOPMENT:
            raise ActorDatasetValidationError("development must have the development split.")
        if self.held_out.split is not ActorSplit.HELD_OUT:
            raise ActorDatasetValidationError("held_out must have the held_out split.")

    def panel(self, split: ActorSplit) -> ActorSplitDataset:
        return self.development if ActorSplit(split) is ActorSplit.DEVELOPMENT else self.held_out

    @property
    def aggregate_evidence_labels(self) -> tuple[EvidenceLabel, ...]:
        """Return the sorted unique evidence labels across all admitted trajectories."""

        return tuple(sorted({
            evidence.label
            for panel in (self.development, self.held_out)
            for trajectory in panel.admitted_trajectories
            for evidence in trajectory.evidence
        }, key=lambda label: label.value))


def load_actor_dataset(
    *,
    development: Iterable[TrustedExperimentSource],
    held_out: Iterable[TrustedExperimentSource],
    accepted_backend_manifest: BackendManifest,
) -> ActorDataset:
    """Load two explicit trusted panels and reject shared canonical episode requests.

    Source ordering is declaration ordering.  Within one source, ordering is
    repetition order, configured episode-panel order, then policy-record ordinal.
    """

    development_sources = _sources(development, "development")
    held_out_sources = _sources(held_out, "held_out")
    if not isinstance(accepted_backend_manifest, BackendManifest):
        raise TypeError("accepted_backend_manifest must be a BackendManifest.")
    development_panel, development_requests = _load_panel(
        ActorSplit.DEVELOPMENT, development_sources, accepted_backend_manifest
    )
    held_out_panel, held_out_requests = _load_panel(
        ActorSplit.HELD_OUT, held_out_sources, accepted_backend_manifest
    )
    if development_requests & held_out_requests:
        raise ActorDatasetValidationError(
            "Development and held-out panels overlap on a canonical episode request."
        )
    return ActorDataset(development_panel, held_out_panel)


def _sources(
    values: Iterable[TrustedExperimentSource], name: str
) -> tuple[TrustedExperimentSource, ...]:
    sources = tuple(values)
    if any(not isinstance(item, TrustedExperimentSource) for item in sources):
        raise TypeError(f"{name} sources must contain TrustedExperimentSource values.")
    return sources


def _load_panel(
    split: ActorSplit,
    sources: tuple[TrustedExperimentSource, ...],
    accepted_backend_manifest: BackendManifest,
) -> tuple[ActorSplitDataset, set[bytes]]:
    examples: list[ActorExample] = []
    admitted_trajectories: list[AdmittedTrajectoryProvenance] = []
    request_keys: set[bytes] = set()
    non_actionable = 0
    no_choice = 0

    for source in sources:
        loaded = _trusted_experiment(source)
        config = loaded.config
        _validate_accepted_pins(accepted_backend_manifest, config.backend_manifest)
        request_by_trajectory_id = {
            episode.trajectory_id: _episode_request_key(config, episode.run_config.to_dict())
            for episode in config.benchmark.batch.episodes
        }
        # Panel separation is a declaration-level safety property.  Pending or
        # failed episodes therefore still participate even when no finalized
        # trajectory supplies an actor sample.
        request_keys.update(request_by_trajectory_id.values())
        for repetition in loaded.report.repetitions:
            for episode in repetition.received:
                trajectory = loaded.trajectories.get(
                    (repetition.repetition_index, episode.trajectory_id)
                )
                if trajectory is None:
                    continue
                _validate_trajectory_pins(config, trajectory)
                if trajectory.manifest_sha256 != episode.trajectory_manifest_sha256:
                    raise ActorDatasetValidationError(
                        "Trusted trajectory manifest digest does not match the experiment report."
                    )
                admitted_trajectories.append(
                    AdmittedTrajectoryProvenance(
                        source.expected_manifest_sha256,
                        repetition.repetition_index,
                        episode.trajectory_id,
                        trajectory.manifest_sha256,
                        trajectory.manifest.evidence,
                    )
                )
                try:
                    records = decode_policy_replay(trajectory.policy_replay_jsonl)
                except TrajectoryValidationError as exc:
                    raise ActorDatasetValidationError(
                        "Trusted policy replay decoding failed."
                    ) from exc
                for ordinal, record in enumerate(records):
                    example, excluded = _actor_example(
                        record,
                        experiment_manifest_sha256=source.expected_manifest_sha256,
                        repetition_index=repetition.repetition_index,
                        trajectory_id=episode.trajectory_id,
                        trajectory_manifest_sha256=trajectory.manifest_sha256,
                        policy_record_ordinal=ordinal,
                    )
                    if excluded == "non_actionable":
                        non_actionable += 1
                    elif excluded == "actionable_without_choice":
                        no_choice += 1
                    elif example is not None:
                        examples.append(example)
                    else:  # Defensive totality guard for future record forms.
                        raise ActorDatasetValidationError("Actor record eligibility was not classified.")

    return (
        ActorSplitDataset(
            split,
            tuple(examples),
            ActorSkipCounts(non_actionable, no_choice),
            tuple(admitted_trajectories),
        ),
        request_keys,
    )


def _trusted_experiment(source: TrustedExperimentSource) -> LoadedHeadlessExperiment:
    try:
        loaded = load_headless_experiment(
            source.root, expected_manifest_sha256=source.expected_manifest_sha256
        )
    except (
        ExperimentIntegrityError,
        ExperimentValidationError,
        TrajectoryValidationError,
        OSError,
    ) as exc:
        raise ActorDatasetValidationError("Trusted experiment loading failed.") from exc
    if loaded.report.sha256 != source.expected_manifest_sha256:
        raise ActorDatasetValidationError("Trusted experiment manifest digest changed after loading.")
    return loaded


def _validate_accepted_pins(
    accepted: BackendManifest, observed: BackendManifest
) -> None:
    """Reject sources outside the caller-declared backend/content/rules/contract pins."""

    pin_fields = (
        "contract",
        "contract_fingerprint",
        "backend_id",
        "backend_version",
        "backend_fingerprint",
        "content_version",
        "content_fingerprint",
        "rules_version",
        "rules_fingerprint",
    )
    if any(getattr(accepted, field) != getattr(observed, field) for field in pin_fields):
        raise ActorDatasetValidationError(
            "Experiment backend/content/rules/contract pins do not match the accepted manifest."
        )


def _episode_request_key(config: HeadlessExperimentConfig, run_config: dict[str, object]) -> bytes:
    """Return the exact Section 3.3 cross-panel identity, excluding display/control fields."""

    manifest = config.backend_manifest
    return canonical_json_bytes(
        {
            "backend_id": manifest.backend_id,
            "backend_version": manifest.backend_version,
            "backend_fingerprint": manifest.backend_fingerprint,
            "content_version": manifest.content_version,
            "content_fingerprint": manifest.content_fingerprint,
            "rules_version": manifest.rules_version,
            "rules_fingerprint": manifest.rules_fingerprint,
            "contract": manifest.contract,
            "contract_fingerprint": manifest.contract_fingerprint,
            "run_config": run_config,
        }
    )


def _validate_trajectory_pins(
    config: HeadlessExperimentConfig, trajectory: FinalizedTrajectory
) -> None:
    expected = config.backend_manifest
    actual = trajectory.manifest
    if (
        actual.contract != expected.contract
        or actual.contract_fingerprint != expected.contract_fingerprint
        or actual.backend_id != expected.backend_id
        or actual.backend_version != expected.backend_version
        or actual.backend_fingerprint != expected.backend_fingerprint
        or actual.content_version != expected.content_version
        or actual.content_fingerprint != expected.content_fingerprint
        or actual.rules_version != expected.rules_version
        or actual.rules_fingerprint != expected.rules_fingerprint
        or actual.evidence != expected.evidence
    ):
        raise ActorDatasetValidationError("Trajectory identity pins do not match its experiment.")


def _actor_example(
    record: PolicyReplayRecord,
    *,
    experiment_manifest_sha256: str,
    repetition_index: int,
    trajectory_id: str,
    trajectory_manifest_sha256: str,
    policy_record_ordinal: int,
) -> tuple[ActorExample | None, str | None]:
    """Convert one policy record without consulting a target or audit sidecar."""

    if not isinstance(record, PolicyReplayRecord):
        raise TypeError("Only PolicyReplayRecord values can become actor examples.")
    view = policy_view_for(record)
    if view.status is not DecisionStatus.ACTIONABLE:
        return None, "non_actionable"
    if record.chosen_action is None:
        return None, "actionable_without_choice"
    chosen_id = record.chosen_action.candidate_id
    if chosen_id not in {candidate.candidate_id for candidate in view.candidates}:
        raise ActorDatasetValidationError("Chosen action is not an advertised candidate.")
    return (
        ActorExample(
            view,
            chosen_id,
            ActorExampleProvenance(
                experiment_manifest_sha256,
                repetition_index,
                trajectory_id,
                trajectory_manifest_sha256,
                policy_record_ordinal,
            ),
        ),
        None,
    )
