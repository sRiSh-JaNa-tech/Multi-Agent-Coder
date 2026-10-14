import os
import sys
from pathlib import Path
from multi_agent_coder.tools.execution import run_sandboxed_command

def test_kills_hanging_process_and_children_on_timeout(tmp_path: Path):
    # Spawn a subprocess that sleeps for 60s
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    res = run_sandboxed_command(cmd, cwd=tmp_path, timeout_seconds=0.5)

    assert res.timed_out is True
    assert res.exit_code == -1
    assert "timeout" in res.stderr.lower()

def test_strips_secret_env_vars_and_truncates_output(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key-123")
    cmd = [
        sys.executable,
        "-c",
        "import os; print(os.environ.get('GEMINI_API_KEY', 'STRIPPED')); print('A' * 10000)",
    ]
    res = run_sandboxed_command(cmd, cwd=tmp_path, max_output_chars=500)

    assert res.exit_code == 0
    assert "super-secret-key-123" not in res.stdout
    assert "STRIPPED" in res.stdout
    assert "TRUNCATED" in res.stdout
    assert len(res.stdout) < 600
