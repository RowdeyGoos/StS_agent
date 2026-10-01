"""Maintained package boundaries and installed command declarations."""

from pathlib import Path
import json
import subprocess
import sys


def test_package_has_only_current_engine_agent_cli_and_bridge_wire_codec():
    root = Path(__file__).resolve().parents[1]
    # Git deletion may leave ignored bytecode directories in an existing checkout.
    packages = {p.relative_to(root / "game").parts[0]
                for p in (root / "game").rglob("*.py")
                if len(p.relative_to(root / "game").parts) > 1}
    assert packages == {"headless", "agent", "cli", "backends"}
    assert {p.stem for p in (root / "game/cli").glob("*.py")} == {
        "__init__", "headless_play", "agent_play", "agent_evaluate", "agent_train", "agent_analyze", "agent_track"}


def test_direct_cli_help_works_without_optional_dependencies():
    result = subprocess.run([sys.executable, "-S", "-m", "game.cli.headless_play", "--help"],
                            capture_output=True, text=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert "--character" in result.stdout and "--verify-restore" in result.stdout


def test_agent_cli_help_works_without_optional_dependencies():
    result = subprocess.run([sys.executable, "-S", "-m", "game.cli.agent_play", "--help"],
                            capture_output=True, text=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert "--workers" in result.stdout and "--split" in result.stdout


def test_combat_cli_help_and_training_data_modules_work_without_optional_dependencies():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-S", "-m", "game.cli.agent_evaluate", "--help"],
                            capture_output=True, text=True, timeout=30, cwd=root)
    assert result.returncode == 0, result.stderr
    assert "--config" in result.stdout and "--split" in result.stdout
    result = subprocess.run([sys.executable, "-S", "-c",
        "from game.agent.training import config, rewards, records, dataset; "
        "assert config.TrainingConfig.load('configs/training/combat_victory.json').reward == rewards.RewardSpec()"],
        capture_output=True, text=True, timeout=30, cwd=root)
    assert result.returncode == 0, result.stderr


def test_training_cli_help_works_without_optional_dependencies():
    result = subprocess.run([sys.executable, "-S", "-m", "game.cli.agent_train", "--help"],
                            capture_output=True, text=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert all(name in result.stdout for name in ('collect','imitate','ppo','curriculum'))
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_train', 'ppo', '--help'],
                            capture_output=True, text=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert '--resume-state' in result.stdout and '--decisions' in result.stdout
    assert '--workers' in result.stdout


def test_tracking_cli_help_and_disabled_reporter_need_no_optional_dependencies():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_track', '--help'],
                            capture_output=True, text=True, timeout=30, cwd=root)
    assert result.returncode == 0 and 'import' in result.stdout and 'serve' in result.stdout
    result = subprocess.run([sys.executable, '-S', '-c',
        "from game.agent.tracking import report_progress; "
        "report_progress('unused/ppo.json', {}); import sys; assert 'mlflow' not in sys.modules"],
        capture_output=True, text=True, timeout=30, cwd=root)
    assert result.returncode == 0, result.stderr


def test_checkpoint_playback_explains_missing_training_dependencies(tmp_path):
    for flag in ('--checkpoint', '--combat-checkpoint'):
        output = tmp_path/flag.removeprefix('--')
        result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_play',
            flag, 'missing.sts-model', '--output-dir', str(output)],
            capture_output=True, text=True, timeout=30, cwd=Path(__file__).resolve().parents[1])
        assert result.returncode == 1 and result.stdout == ''
        error = json.loads(result.stderr)
        assert error['status'] == 'failed' and error['category'] == 'ModuleNotFoundError'
        assert 'sts-agent[train]' in error['reason']
        assert not output.exists()


def test_curriculum_cli_rejects_malformed_json_shapes_without_traceback(tmp_path):
    import pytest
    pytest.importorskip('torch')
    pytest.importorskip('gymnasium')
    for index, change in enumerate(({'decisions':None}, {'decisions':3}, {'ppo':None},
                                    {'ppo':[]}, {'ppo':{'batch_szie':1}})):
        config = tmp_path/f'config-{index}.json'
        config.write_text(json.dumps({'decisions':[1]*5, 'ppo':{}, 'stage_seconds':10, **change}))
        output = tmp_path/f'output-{index}'
        result = subprocess.run([sys.executable, '-m', 'game.cli.agent_train', 'curriculum',
            '--checkpoint', 'missing.sts-model', '--config', str(config), '--output-dir', str(output)],
            capture_output=True, text=True, timeout=30, cwd=Path(__file__).resolve().parents[1])
        assert result.returncode == 2 and 'Expected complete curriculum settings' in result.stderr
        assert 'Traceback' not in result.stderr and not output.exists()
