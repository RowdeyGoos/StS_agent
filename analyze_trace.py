"""Analyze one saved combat trace and flag common tactical mistakes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from game.trace_analysis import analyze_episode_trace, format_finding
from game.watch import load_episode_trace


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for trace analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze a saved combat trace and summarize likely mistakes."
    )
    parser.add_argument(
        "trace_path",
        type=str,
        help="Path to a JSON trace produced by watch_policy.py.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=20,
        help="Maximum number of findings to print.",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional output path for saving the structured analysis report.",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Run the trace analyzer and print a compact report."""
    args = parse_args()
    trace = load_episode_trace(args.trace_path)
    report = analyze_episode_trace(trace)

    print(
        f"Trace analysis: policy={report.policy_name} seed={report.seed} "
        f"steps={report.total_steps} findings={len(report.findings)}"
    )
    if report.category_counts:
        print("Category counts:")
        for category, count in report.category_counts.items():
            print(f"  {category}: {count}")

    if report.findings:
        print("\nTop findings:")
        for finding in report.findings[: max(1, args.max_findings)]:
            print(f"  - {format_finding(finding, trace=trace)}")
    else:
        print("\nNo high-confidence tactical mistakes were flagged.")

    if args.json_out is not None:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report.as_dict(), indent=2),
            encoding="utf-8",
        )
        print(f"\nSaved analysis report to {args.json_out}")


if __name__ == "__main__":
    main()
