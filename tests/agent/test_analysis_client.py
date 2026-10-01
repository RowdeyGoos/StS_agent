"""Run the viewer's JavaScript regression tests when Node.js is available."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_analysis_client_request_recovery():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js is required for the analysis viewer client tests')
    suite = Path(__file__).with_name('analysis_client.test.cjs')
    result = subprocess.run([node, '--test', str(suite)], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
