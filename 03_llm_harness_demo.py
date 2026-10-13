"""
Root Entry Point for LLM Harness Demonstration.
Seamlessly routes execution to codebase-navigator/03_llm_harness_demo.py.
"""

import sys
import runpy
from pathlib import Path

# Ensure codebase-navigator directory is in sys.path
_ROOT = Path(__file__).resolve().parent
_NAV_DIR = _ROOT / "codebase-navigator"

if str(_NAV_DIR) not in sys.path:
    sys.path.insert(0, str(_NAV_DIR))

if __name__ == "__main__":
    target_script = _NAV_DIR / "03_llm_harness_demo.py"
    runpy.run_path(str(target_script), run_name="__main__")
