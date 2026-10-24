import os
import logging
import logging.handlers
from pathlib import Path

# ── Ensure logs directory exists ──────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Read log level from environment (default DEBUG for dev) ───────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()

# ── Shared formatter: timestamp · module · function · line ────────────────────
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

# ── Handlers ──────────────────────────────────────────────────────────────────
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(formatter)
_console_handler.setLevel(LOG_LEVEL)

_file_handler = logging.handlers.RotatingFileHandler(
    filename=LOGS_DIR / "app.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(formatter)
_file_handler.setLevel(LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger pre-configured with console + rotating-file handlers.
    Call once per module: ``logger = get_logger(__name__)``
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_console_handler)
        logger.addHandler(_file_handler)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    return logger
