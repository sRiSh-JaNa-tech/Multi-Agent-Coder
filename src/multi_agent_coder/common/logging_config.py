"""
Logging Configuration
Provides standardized Rich-enhanced logging.
"""

import logging
import os
import sys
from pathlib import Path
from rich.logging import RichHandler

# Repo root: <repo>/src/multi_agent_coder/common/logging_config.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LOG_DIR = _REPO_ROOT / "logs"
_DEFAULT_LOG_FILE = _DEFAULT_LOG_DIR / "swarm.log"

_FILE_HANDLER: logging.FileHandler | None = None


def _get_file_handler(target_file: Path | str | None = None) -> logging.FileHandler | None:
    """Create or return a thread-safe FileHandler for persistent logs."""
    global _FILE_HANDLER
    if _FILE_HANDLER is not None and target_file is None:
        return _FILE_HANDLER

    log_path: Path
    if target_file is not None:
        log_path = Path(target_file).resolve()
    else:
        custom_file = os.getenv("SWARM_LOG_FILE")
        if custom_file:
            log_path = Path(custom_file).resolve()
        else:
            custom_dir = os.getenv("SWARM_LOG_DIR")
            if custom_dir:
                log_path = Path(custom_dir).resolve() / "swarm.log"
            else:
                log_path = _DEFAULT_LOG_FILE

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(log_path), encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
        handler.setFormatter(formatter)
        if target_file is None:
            _FILE_HANDLER = handler
        return handler
    except OSError:
        return None


def setup_logging(
    name: str = __name__,
    level: int = logging.INFO,
    log_file: Path | str | None = None,
) -> logging.Logger:
    """Configure and return a standardized logger with Rich console and persistent file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 1. Console Rich Handler
    has_rich = any(isinstance(h, RichHandler) for h in logger.handlers)
    if not has_rich:
        console_handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=False,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    # 2. Persistent File Handler
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    if not has_file:
        file_handler = _get_file_handler(log_file)
        if file_handler is not None:
            logger.addHandler(file_handler)

    logger.propagate = False
    return logger

