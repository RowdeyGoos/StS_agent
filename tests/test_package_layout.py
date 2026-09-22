"""Maintained package boundaries and installed command declarations."""

from pathlib import Path
import subprocess
import sys


def test_package_has_only_current_engine_cli_and_bridge_wire_codec():
    root = Path(__file__).resolve().parents[1]
    # Git deletion may leave ignored bytecode directories in an existing checkout.
    packages = {p.relative_to(root / "game").parts[0]
                for p in (root / "game").rglob("*.py")
                if len(p.relative_to(root / "game").parts) > 1}
    assert packages == {"headless", "cli", "backends"}
    assert {p.stem for p in (root / "game/cli").glob("*.py")} == {"__init__", "headless_play"}


def test_direct_cli_help_works_without_optional_dependencies():
    result = subprocess.run([sys.executable, "-S", "-m", "game.cli.headless_play", "--help"],
                            capture_output=True, text=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert "--character" in result.stdout and "--verify-restore" in result.stdout
