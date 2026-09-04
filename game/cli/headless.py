"""Bounded command-line experiments for the reduced headless backend.

The command is deliberately only a configuration adapter.  Episode collection,
benchmarking, and artifact persistence remain owned by their existing modules.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from json import JSONDecodeError
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from game.backends.headless.reduced_run_backend import HeadlessRunConfig, create_reduced_run_backend
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.training.headless_benchmark import HeadlessBenchmarkConfig, benchmark_headless_rollouts
from game.training.headless_reporting import (
    HeadlessExperimentConfig,
    ExperimentValidationError,
    load_headless_experiment,
    preflight_headless_experiment_output,
    write_headless_experiment,
)
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
    RolloutStopReason,
)


_MAX_CONFIG_BYTES = 1_048_576
_CONFIG_FIELDS = frozenset({
    "episodes", "experiment_id", "output_root", "process_safe", "repetitions",
    "worker_count", "worker_seed",
})
_EPISODE_FIELDS = frozenset({
    "chooser_kind", "game_seed", "policy_seed", "scenario_id", "settings",
    "trajectory_id", "transition_budget",
})


def _read_json_object(path: Path) -> Mapping[str, Any]:
    """Read a small duplicate-key-free configuration object."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read configuration: {exc}") from exc
    if len(raw) > _MAX_CONFIG_BYTES:
        raise ValueError("Configuration exceeds its byte limit.")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Configuration contains duplicate field {key!r}.")
            value[key] = item
        return value

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise ValueError("Configuration must be valid UTF-8 JSON.") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Configuration must contain an object.")
    return value


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unknown {', '.join(unknown)}")
        raise ValueError(f"{label} fields are not exact ({'; '.join(details)}).")


def _integer(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be an integer <= {maximum}.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _parse_panel(value: Mapping[str, Any], output_root_override: str | None) -> tuple[Path, HeadlessBenchmarkConfig, str]:
    """Validate direct user declarations before any backend is constructed."""

    _exact_fields(value, _CONFIG_FIELDS, "configuration")
    experiment_id = _text(value["experiment_id"], "experiment_id")
    output_text = output_root_override if output_root_override is not None else _text(value["output_root"], "output_root")
    output_root = Path(output_text)
    if not output_text.strip():
        raise ValueError("output_root must not be blank.")
    if not isinstance(value["process_safe"], bool):
        raise ValueError("process_safe must be boolean.")
    worker = CollectorWorkerConfig(
        _integer(value["worker_count"], "worker_count", minimum=1, maximum=32),
        _integer(value["worker_seed"], "worker_seed"),
    )
    repetitions = _integer(value["repetitions"], "repetitions", minimum=1, maximum=32)
    raw_episodes = value["episodes"]
    if not isinstance(raw_episodes, list) or not raw_episodes:
        raise ValueError("episodes must be a nonempty array.")
    if len(raw_episodes) > 64:
        raise ValueError("episodes may contain at most 64 items.")
    episodes: list[HeadlessRolloutConfig] = []
    for index, raw_episode in enumerate(raw_episodes):
        if not isinstance(raw_episode, Mapping):
            raise ValueError(f"episodes[{index}] must be an object.")
        _exact_fields(raw_episode, _EPISODE_FIELDS, f"episodes[{index}]")
        settings = raw_episode["settings"]
        if not isinstance(settings, Mapping):
            raise ValueError(f"episodes[{index}].settings must be an object.")
        try:
            chooser_kind = ChooserKind(raw_episode["chooser_kind"])
            run_config = HeadlessRunConfig(
                _text(raw_episode["scenario_id"], f"episodes[{index}].scenario_id"),
                # The accepted backend validates this declared pin during reset.
                # It is filled from the known reduced-content identity below.
                CONTENT_FINGERPRINT,
                _integer(raw_episode["game_seed"], f"episodes[{index}].game_seed"),
                dict(settings),
            )
            episodes.append(HeadlessRolloutConfig(
                _text(raw_episode["trajectory_id"], f"episodes[{index}].trajectory_id"),
                run_config,
                _integer(raw_episode["transition_budget"], f"episodes[{index}].transition_budget", maximum=300),
                chooser_kind=chooser_kind,
                policy_seed=_integer(raw_episode["policy_seed"], f"episodes[{index}].policy_seed"),
            ))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"episodes[{index}] is invalid: {exc}") from exc
    try:
        benchmark = HeadlessBenchmarkConfig(
            HeadlessBatchConfig(tuple(episodes), worker), repetitions=repetitions,
            process_safe=value["process_safe"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Benchmark configuration is invalid: {exc}") from exc
    return output_root, benchmark, experiment_id


def _experiment_config(experiment_id: str, benchmark: HeadlessBenchmarkConfig) -> HeadlessExperimentConfig:
    """Obtain only the accepted backend manifest after user config preflight."""

    backend = create_reduced_run_backend()
    try:
        return HeadlessExperimentConfig(experiment_id, benchmark, backend.manifest())
    finally:
        backend.close()


def _summarize(result: Any, report: Any) -> str:
    reasons = Counter(
        item.stop_reason.value
        for batch in result.batches
        for item in batch.results
    )
    reason_text = ", ".join(f"{reason}={reasons[reason]}" for reason in sorted(reasons)) or "none"
    pending = sum(len(item.pending_trajectory_ids) for item in report.repetitions)
    return (
        f"experiment_manifest_sha256={report.sha256}\n"
        f"attempted_repetitions={result.attempted_repetitions} "
        f"unstarted_repetitions={result.unstarted_repetitions}\n"
        f"pending_trajectory_ids={pending}\n"
        f"stop_reasons={reason_text}"
    )


def _run_command(args: argparse.Namespace, *, require_single_repetition: bool) -> None:
    raw = _read_json_object(Path(args.config))
    output_root, benchmark, experiment_id = _parse_panel(raw, args.output_root)
    if require_single_repetition and benchmark.repetitions != 1:
        raise ValueError("run requires repetitions to be exactly one; use benchmark for repeated collection.")
    # This rejection is deliberately before manifest/backend creation and before
    # collector execution.  The writer repeats it atomically before writing.
    preflight_headless_experiment_output(output_root)
    config = _experiment_config(experiment_id, benchmark)
    result = benchmark_headless_rollouts(config.benchmark)
    report = write_headless_experiment(output_root, config, result)
    print(_summarize(result, report))


def _validate_command(args: argparse.Namespace) -> None:
    loaded = load_headless_experiment(
        args.output_root, expected_manifest_sha256=args.manifest_sha256,
    )
    print(
        f"validated_experiment_id={loaded.config.experiment_id}\n"
        f"repetitions={len(loaded.report.repetitions)}\n"
        f"trajectories={len(loaded.trajectories)}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded reduced-headless experiment panels.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name, description in (
        ("run", "Collect exactly one configured panel."),
        ("benchmark", "Collect the configured repeated benchmark panel."),
    ):
        command = subcommands.add_parser(name, help=description)
        command.add_argument("--config", required=True, help="Exact JSON experiment-panel declaration.")
        command.add_argument("--output-root", default=None, help="Override the declared new artifact directory.")
    validate = subcommands.add_parser("validate", help="Load a finalized artifact using a caller-held manifest hash.")
    validate.add_argument("--output-root", required=True, help="Finalized experiment artifact directory.")
    validate.add_argument("--manifest-sha256", required=True, help="Externally supplied SHA-256 of experiment.manifest.json.")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run one bounded command without importing optional RL packages."""

    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            _run_command(args, require_single_repetition=True)
        elif args.command == "benchmark":
            _run_command(args, require_single_repetition=False)
        else:
            _validate_command(args)
    except (ExperimentValidationError, FileExistsError, OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"Headless command failed: {exc}") from exc


if __name__ == "__main__":
    main()
