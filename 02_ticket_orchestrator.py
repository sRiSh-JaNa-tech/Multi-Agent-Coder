"""
Root Entry Point for Ticket Orchestrator.
Seamlessly routes execution to codebase-navigator/02_ticket_orchestrator.py.
"""

import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_NAV_DIR = _ROOT / "codebase-navigator"

if str(_NAV_DIR) not in sys.path:
    sys.path.insert(0, str(_NAV_DIR))

if __name__ == "__main__":
    target_script = _NAV_DIR / "02_ticket_orchestrator.py"
    runpy.run_path(str(target_script), run_name="__main__")
