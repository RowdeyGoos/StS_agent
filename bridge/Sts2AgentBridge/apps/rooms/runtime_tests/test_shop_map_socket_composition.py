"""Run the frozen runtime socket fixture against the repaired composition."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


FROZEN = (
    Path(__file__).absolute().parents[2]
    / "rooms"
    / "integration"
    / "test_socket_composition.py"
)


def _load_frozen():
    specification = importlib.util.spec_from_file_location(
        "shop_map_permission_frozen_socket_composition",
        FROZEN,
    )
    if specification is None or specification.loader is None:
        raise ValueError("frozen_socket_composition_unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True)
    parser.add_argument("--fixture", required=True)
    arguments = parser.parse_args()
    _load_frozen().run_suite(arguments.dotnet, arguments.fixture)
