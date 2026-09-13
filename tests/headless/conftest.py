"""Explicit historical reward fixtures for route-policy regression scenarios."""

from dataclasses import replace
import pytest
from game.headless.run.engine import RunEngine


@pytest.fixture
def original_slice_rewards(monkeypatch):
    # These tests certify an existing demo-policy victory, whose deck depended on
    # the original narrow reward pool. Full-pool acquisition is tested separately.
    original = RunEngine.ironclad_slice.__func__

    def create(cls, **kwargs):
        run = original(cls, **kwargs)
        pool = (
            "pommel_strike",
            "shrug_it_off",
            "iron_wave",
            "body_slam",
            "armaments",
            "true_grit",
            "uppercut",
        )
        if kwargs.get("route") == "overgrowth-act1":
            pool += ("sword_boomerang",)
        run.state.config = replace(
            run.state.config, reward_cards=pool, boss_reward_cards=("impervious", "offering", "fiend_fire")
        )
        return run

    monkeypatch.setattr(RunEngine, "ironclad_slice", classmethod(create))
