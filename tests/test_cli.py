from __future__ import annotations

import subprocess
import sys


def test_doctor_cli_runs_native_smoke_test() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "zh_catmut", "doctor"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Loaded native ABI" in result.stdout
    assert "Native smoke test passed" in result.stdout
