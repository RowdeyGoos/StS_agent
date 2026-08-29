"""CLI for the resumable full-system benchmark campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from game.analysis.benchmark_suite import (
    BenchmarkSuiteManifest,
    confirmation_training_specs,
    hard_training_specs,
    load_suite_manifest,
    run_full_benchmark_suite,
    screen_training_specs,
    time_training_specs,
    training_command,
)

DEFAULT_MANIFEST_PATH = "configs/full_system_benchmark_balanced.json"
ALL_STAGES = (
    "inventory",
    "card_encoding",
    "screen",
    "confirmation",
    "time",
    "hard",
    "oracle",
    "report",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or resume the controlled multi-model, multi-deck benchmark campaign."
        )
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_MANIFEST_PATH,
        help="Versioned benchmark-suite JSON manifest.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output-directory override.",
    )
    parser.add_argument(
        "--stage",
        action="append",
        choices=ALL_STAGES,
        default=None,
        help=(
            "Run selected stages. Repeat as needed; omitted runs the complete campaign. "
            "Skipped dependency stages must already have resumable artifacts."
        ),
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse completed trainer and evaluation cells.",
    )
    parser.add_argument(
        "--mini",
        action="store_true",
        help="Use a tiny three-policy smoke campaign instead of production budgets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved configuration and the stage-one commands without running.",
    )
    return parser.parse_args(argv)


def resolve_manifest(args: argparse.Namespace) -> BenchmarkSuiteManifest:
    manifest = load_suite_manifest(args.config)
    output_dir = args.output_dir or manifest.output_dir
    if args.mini:
        return manifest.miniature(output_dir)
    if output_dir != manifest.output_dir:
        from dataclasses import replace

        manifest = replace(manifest, output_dir=output_dir)
    return manifest


def dry_run_payload(manifest: BenchmarkSuiteManifest) -> dict[str, object]:
    screen_specs = screen_training_specs(manifest)
    return {
        "manifest": manifest.as_dict(),
        "counts": {
            "screen_runs": len(screen_specs),
            "confirmation_runs_after_four_selected": len(
                confirmation_training_specs(manifest, manifest.variants[:4])
            ),
            "time_runs_after_four_selected": len(
                time_training_specs(manifest, manifest.variants[:4])
            ),
            "hard_runs_after_three_selected": len(
                hard_training_specs(manifest, manifest.variants[:3])
            ),
        },
        "screen_commands": [list(training_command(manifest, spec)) for spec in screen_specs],
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        manifest = resolve_manifest(args)
        if args.dry_run:
            print(json.dumps(dry_run_payload(manifest), indent=2, sort_keys=True))
            return
        default_stages = (
            tuple(stage for stage in ALL_STAGES if stage not in {"time", "oracle"})
            if args.mini
            else ALL_STAGES
        )
        report = run_full_benchmark_suite(
            manifest,
            stages=default_stages if args.stage is None else tuple(args.stage),
            resume=args.resume,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Benchmark suite complete: {Path(manifest.output_dir) / 'report.md'}")
    if report.get("controlled_rankings", {}).get("confirmation"):
        leader = report["controlled_rankings"]["confirmation"][0]["variant"]
        print(f"Controlled confirmation leader: {leader}")


if __name__ == "__main__":
    main()
