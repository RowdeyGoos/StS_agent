"""Run the frozen room-flow host fixture against the repaired C# service."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


FROZEN = (
    Path(__file__).absolute().parents[3]
    / "components/rooms"
    / "integration"
    / "test_cross_language.py"
)


def _load_frozen():
    specification = importlib.util.spec_from_file_location(
        "shop_map_permission_frozen_cross_language",
        FROZEN,
    )
    if specification is None or specification.loader is None:
        raise ValueError("frozen_cross_language_unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--item-host", required=True)
    arguments = parser.parse_args()
    _load_frozen().run_suite(
        arguments.dotnet,
        arguments.fixture,
        arguments.item_host,
    )
