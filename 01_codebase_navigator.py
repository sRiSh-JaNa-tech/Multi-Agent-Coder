"""
Root Entry Point for Codebase Navigator.
Seamlessly routes execution to codebase-navigator/01_codebase_navigator.py.
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
    target_script = _NAV_DIR / "01_codebase_navigator.py"
    runpy.run_path(str(target_script), run_name="__main__")
