import sys
from pathlib import Path

import pytest

# Ensure src directory is in sys.path for test discovery
root = Path(__file__).resolve().parent.parent
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))


@pytest.fixture(autouse=True)
def _hermetic_swarm_env(monkeypatch, tmp_path):
    """Keep tests independent of the developer's .env and out of the real log dir."""
    monkeypatch.setenv("SWARM_LOG_DIR", str(tmp_path / "swarm_logs"))
    for name in (
        "TARGET_WORKSPACE",
        "TOKEN_USAGE_LIMIT",
        "MAX_TOKENS",
        "MODEL_NAME",
        "GEMINI_MODEL",
        "AGENT_NAMES",
    ):
        monkeypatch.delenv(name, raising=False)
