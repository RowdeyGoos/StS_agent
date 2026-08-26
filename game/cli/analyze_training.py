"""Print bottleneck and resource summaries from saved training profiles."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from game.training.profile import (
    load_training_profile,
    print_training_profile_payload,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze profile.json files produced by sts-train --profile-training."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more profile JSON files or run directories containing profile.json.",
    )
    parser.add_argument(
        "--max-phases",
        type=int,
        default=12,
        help="Maximum phase rows printed for each profile.",
    )
    args = parser.parse_args(argv)
    if args.max_phases <= 0:
        parser.error("--max-phases must be positive.")
    return args


def main() -> None:
    args = parse_args()
    for index, raw_path in enumerate(args.paths):
        path = Path(raw_path)
        if len(args.paths) > 1:
            if index > 0:
                print()
            print(f"Profile: {path}")
        payload = load_training_profile(path)
        print_training_profile_payload(payload, max_phases=args.max_phases)


if __name__ == "__main__":
    main()
