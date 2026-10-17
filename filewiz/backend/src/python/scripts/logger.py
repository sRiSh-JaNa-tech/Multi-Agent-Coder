import logging
import os

# 🔒 Resolve path relative to THIS file, not cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'logs'))
LOG_FILE = os.path.join(LOG_DIR, 'file.log')

# ✅ Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',  # 👈 append (IMPORTANT)
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)

def log(message: str, level: str = 'DEBUG', module_name: str = None) -> None:
    logger = logging.getLogger(module_name or __name__)
    level_upper = level.upper()

    mapping = logging.getLevelNamesMapping()
    if level_upper in mapping:
        logger.log(mapping[level_upper], message)
    else:
        logger.error(f"Invalid log level: {level}. Message: {message}")
