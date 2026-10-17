"""
Logging Configuration
Provides standardized Rich-enhanced logging.
"""

import logging
import sys
from rich.logging import RichHandler


def setup_logging(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a standardized logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=False,
        )
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger
