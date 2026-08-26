"""CLI encounter-registry integration tests."""

from game.cli import sweep, train


def test_training_clis_accept_partial_hard_pool() -> None:
    train_args = train.parse_args(["--encounter-set", "overgrowth_hard_v1"])
    sweep_args = sweep.parse_args(["--encounter-set", "overgrowth_hard_v1"])

    assert train_args.encounter_set == "overgrowth_hard_v1"
    assert sweep_args.encounter_set == "overgrowth_hard_v1"
