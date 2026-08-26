"""Tests for canonical package paths and command implementations."""

from __future__ import annotations

import importlib

import game
from game.agents import ppo
from game.analysis import bruteforce
from game.cli import brute_force, sweep, train, watch_policy
from game.simulation import core
from game.training import profile


def test_public_symbols_come_from_canonical_modules() -> None:
    assert game.CombatEnv is core.CombatEnv
    assert game.PPOAgent is ppo.PPOAgent
    assert game.brute_force_combat is bruteforce.brute_force_combat


def test_packaged_cli_modules_are_directly_usable() -> None:
    assert train.parse_args([]).policy == "compare"
    assert sweep.parse_args([]).policy == "double_dqn"
    assert watch_policy.parse_args(["--policy", "heuristic"]).policy == "heuristic"
    assert brute_force.parse_args([]).encounter == "simple"
    assert profile.TrainingProfiler is not None


def test_removed_flat_module_paths_do_not_silently_resolve() -> None:
    try:
        importlib.import_module("game.core")
    except ModuleNotFoundError:
        return
    raise AssertionError("Legacy game.core unexpectedly remains importable.")
