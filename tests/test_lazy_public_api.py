"""Compatibility checks for the lazy package-level public API."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd())
    return environment


def test_package_import_and_headless_help_do_not_attempt_optional_rl_imports() -> None:
    script = r'''
import importlib.abc
import runpy
import sys

class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "torch" or fullname.startswith("torch.") or fullname == "gymnasium" or fullname.startswith("gymnasium."):
            raise AssertionError("optional import attempted: " + fullname)
        return None

sys.meta_path.insert(0, BlockOptional())
import game
assert "torch" not in sys.modules
assert "gymnasium" not in sys.modules
sys.argv = ["game.cli.headless", "--help"]
try:
    runpy.run_module("game.cli.headless", run_name="__main__")
except SystemExit as exc:
    assert exc.code == 0
'''
    result = subprocess.run(
        [sys.executable, "-c", script], text=True, capture_output=True,
        check=False, env=_environment(), timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_all_public_symbols_keep_canonical_identity_and_import_star_behavior() -> None:
    import game

    assert set(game.__all__) == set(game._PUBLIC_SOURCES)
    for name, source in game._PUBLIC_SOURCES.items():
        assert getattr(game, name) is getattr(importlib.import_module(source, "game"), name)

    namespace: dict[str, object] = {}
    exec("from game import *", namespace)
    assert set(game.__all__) <= set(namespace)
    assert all(namespace[name] is getattr(game, name) for name in game.__all__)
    assert "CombatEnv" in dir(game)
    with pytest.raises(AttributeError):
        getattr(game, "not_a_public_symbol")
