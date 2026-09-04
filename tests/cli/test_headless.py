"""Subprocess coverage for the bounded reduced-headless command."""

from __future__ import annotations

from argparse import Namespace
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import select
import subprocess
import sys

import pytest

from game.cli import headless


def _panel(*, process_safe: bool = False, repetitions: int = 1, episodes: int = 1) -> dict:
    return {
        "episodes": [
            {
                "chooser_kind": "structural_heuristic",
                "game_seed": index + 7,
                "policy_seed": index + 11,
                "scenario_id": "simple__starter",
                "settings": {},
                "trajectory_id": f"cli-headless-{index:03d}",
                "transition_budget": 16,
            }
            for index in range(episodes)
        ],
        "experiment_id": "cli-headless",
        "output_root": "unused-by-test",
        "process_safe": process_safe,
        "repetitions": repetitions,
        "worker_count": 2 if process_safe else 1,
        "worker_seed": 17,
    }


def _write_panel(path: Path, **kwargs: object) -> Path:
    path.write_text(json.dumps(_panel(**kwargs)), encoding="utf-8")
    return path


def _command(*args: str) -> list[str]:
    return [sys.executable, "-m", "game.cli.headless", *args]


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd())
    return environment


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command(*args), text=True, capture_output=True, check=False,
        env=_environment(), timeout=60,
    )


def _report_without_measurement(path: Path) -> dict:
    report = json.loads((path / "experiment.manifest.json").read_text(encoding="utf-8"))
    report.pop("measurement")
    # This report field commits to the declared collector mode.  It is not a
    # semantic trajectory fact, so compare it through the normalized config.
    report.pop("config_sha256")
    return report


def _config_without_mode(path: Path) -> dict:
    config = json.loads((path / "experiment.config.json").read_text(encoding="utf-8"))
    config["benchmark"].pop("process_safe")
    config["benchmark"]["batch"]["worker"].pop("worker_count")
    return config


def test_help_and_smoke_config_do_not_require_optional_rl_packages() -> None:
    help_result = _run("--help")
    assert help_result.returncode == 0
    assert "{run,benchmark,validate}" in help_result.stdout
    sample = Path("configs/headless_smoke.json")
    assert json.loads(sample.read_text(encoding="utf-8"))["experiment_id"] == "headless-smoke"


def test_serial_and_spawned_panels_have_equal_deterministic_artifacts(tmp_path: Path) -> None:
    serial_config = _write_panel(tmp_path / "serial.json", episodes=2)
    spawned_config = _write_panel(tmp_path / "spawned.json", process_safe=True, episodes=2)
    serial_root = tmp_path / "serial"
    spawned_root = tmp_path / "spawned"

    serial = _run("run", "--config", str(serial_config), "--output-root", str(serial_root))
    spawned = _run("run", "--config", str(spawned_config), "--output-root", str(spawned_root))

    assert serial.returncode == 0, serial.stderr
    assert spawned.returncode == 0, spawned.stderr
    assert _config_without_mode(serial_root) == _config_without_mode(spawned_root)
    assert _report_without_measurement(serial_root) == _report_without_measurement(spawned_root)
    serial_files = sorted(path.relative_to(serial_root) for path in serial_root.rglob("*.jsonl"))
    assert serial_files == sorted(path.relative_to(spawned_root) for path in spawned_root.rglob("*.jsonl"))
    for relative_path in serial_files:
        assert (serial_root / relative_path).read_bytes() == (spawned_root / relative_path).read_bytes()


def test_validation_requires_caller_held_manifest_hash(tmp_path: Path) -> None:
    config = _write_panel(tmp_path / "panel.json")
    root = tmp_path / "artifact"
    result = _run("run", "--config", str(config), "--output-root", str(root))
    assert result.returncode == 0, result.stderr
    digest = sha256((root / "experiment.manifest.json").read_bytes()).hexdigest()

    accepted = _run("validate", "--output-root", str(root), "--manifest-sha256", digest)
    rejected = _run("validate", "--output-root", str(root), "--manifest-sha256", "0" * 64)

    assert accepted.returncode == 0, accepted.stderr
    assert "validated_experiment_id=cli-headless" in accepted.stdout
    assert rejected.returncode != 0


def test_invalid_config_and_output_collision_precede_backend_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = _panel()
    invalid["unknown"] = True
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    invalid_id = _panel()
    invalid_id["episodes"][0]["trajectory_id"] = "../bad"
    invalid_id_path = tmp_path / "invalid-id.json"
    invalid_id_path.write_text(json.dumps(invalid_id), encoding="utf-8")
    existing_root = tmp_path / "existing"
    existing_root.mkdir()
    calls = 0

    def no_backend():
        nonlocal calls
        calls += 1
        raise AssertionError("backend construction must not happen")

    monkeypatch.setattr(headless, "create_reduced_run_backend", no_backend)
    with pytest.raises(ValueError):
        headless._run_command(Namespace(config=str(invalid_path), output_root=str(tmp_path / "new")), require_single_repetition=True)
    with pytest.raises(ValueError):
        headless._run_command(Namespace(config=str(invalid_id_path), output_root=str(tmp_path / "new-id")), require_single_repetition=True)
    valid_path = _write_panel(tmp_path / "valid.json")
    with pytest.raises(FileExistsError):
        headless._run_command(Namespace(config=str(valid_path), output_root=str(existing_root)), require_single_repetition=True)
    assert calls == 0


def test_configuration_reader_is_bounded_and_rejects_nonregular_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (headless._MAX_CONFIG_BYTES + 1))
    with pytest.raises(ValueError, match="byte limit"):
        headless._read_json_object(oversized)
    fifo = tmp_path / "config.fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular"):
        headless._read_json_object(fifo)
    external = tmp_path / "external.json"
    external.write_text('{"unexpected":"external"}', encoding="utf-8")
    raced = tmp_path / "raced.json"
    raced.write_text("{}", encoding="utf-8")
    original_open = os.open

    def replace_with_symlink(path: str | bytes | os.PathLike[str], flags: int, *args: object) -> int:
        if Path(path) == raced:
            raced.unlink()
            raced.symlink_to(external)
        return original_open(path, flags, *args)

    monkeypatch.setattr(headless.os, "open", replace_with_symlink)
    with pytest.raises(ValueError, match="regular"):
        headless._read_json_object(raced)


def test_sigint_writes_received_and_pending_artifacts_without_lingering_cli_processes(tmp_path: Path) -> None:
    config = _panel(process_safe=True, repetitions=3, episodes=2)
    for episode in config["episodes"]:
        episode["transition_budget"] = 0
    config_path = tmp_path / "sigint.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    root = tmp_path / "interrupted"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import multiprocessing\nimport os\nimport signal\nimport sys\n"
                "import game.training.headless_rollout as rollout\n"
                "from game.cli.headless import main\n"
                "context = multiprocessing.get_context('spawn')\n"
                "class Pool:\n"
                " def __init__(self):\n  self.pool=context.Pool(processes=2)\n  self.fired=False\n"
                " def imap_unordered(self, fn, entries):\n"
                "  for item in self.pool.imap_unordered(fn, entries):\n"
                "   yield item\n"
                "   if not self.fired:\n    self.fired=True\n    os.kill(os.getpid(), signal.SIGINT)\n"
                " def close(self): self.pool.close()\n"
                " def join(self): self.pool.join()\n"
                " def terminate(self): self.pool.terminate()\n"
                "class Context:\n"
                " def Pool(self, *, processes): return Pool()\n"
                "rollout.get_context=lambda method: Context()\n"
                "print('READY', flush=True)\nmain(sys.argv[1:])\n"
                "print(f'ACTIVE_WORKERS={len(multiprocessing.active_children())}', flush=True)"
            ),
            "benchmark", "--config", str(config_path), "--output-root", str(root),
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_environment(), start_new_session=True,
    )
    try:
        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 30)
        assert readable
        assert process.stdout.readline() == "READY\n"
        stdout, stderr = process.communicate(timeout=60)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=10)

    assert process.returncode == 0, stderr
    assert "unstarted_repetitions=" in stdout
    assert "ACTIVE_WORKERS=0" in stdout
    report = json.loads((root / "experiment.manifest.json").read_text(encoding="utf-8"))
    assert report["repetitions"][0]["interrupted"] is True
    assert report["repetitions"][0]["pending_trajectory_ids"]
    assert report["unstarted_repetition_indices"]
    received = report["repetitions"][0]["received"]
    assert len(received) == 1
    trajectory_id = received[0]["trajectory_id"]
    manifest_digest = sha256((root / "experiment.manifest.json").read_bytes()).hexdigest()
    validated = _run("validate", "--output-root", str(root), "--manifest-sha256", manifest_digest)
    assert validated.returncode == 0, validated.stderr
    assert (root / "repetitions" / "000000" / f"{trajectory_id}.manifest.json").is_file()
