"""Centralized logging for hermes-smartthings.

Features:
- Timestamp + level + function/line in every line
- Automatic sensitive-data redaction (tokens, passwords, secrets)
- RotatingFileHandler: 50 MB per file
- TimedRotatingFileHandler: 7-day retention (keeps last 7 daily backups)
- Log to ~/.hermes/logs/smartthings.log
- Log level configurable in ~/.hermes/smartthings_config.json under "log_level"
"""
import json
import logging
import logging.handlers
import os
import re
from pathlib import Path

LOG_DIR = Path.home() / ".hermes" / "logs"
LOG_FILE = LOG_DIR / "smartthings.log"
MAX_BYTES = 50 * 1024 * 1024      # 50 MB
BACKUP_COUNT = 7                  # 7 days/rotations kept
CONFIG_FILE = Path.home() / ".hermes" / "smartthings_config.json"

# Patterns to redact in log messages
_REDACT_PATTERNS = [
    # Bearer tokens, API keys, PATs
    (re.compile(r'(Authorization\s*[:=]\s*Bearer\s+)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(api[_-]?key\s*[:=]\s*)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(token\s*[:=]\s*)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(pat-)[\w\-]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(client_secret\s*[:=]\s*)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(password\s*[:=]\s*)[^\s\&]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(refresh_token\s*[:=]\s*)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    (re.compile(r'(access_token\s*[:=]\s*)[\w\-\.]+', re.I), r'\1***REDACTED***'),
    # JSON values that look like tokens
    (re.compile(r'"(token|access_token|refresh_token|client_secret|api_key|password)"\s*:\s*"[^"]{8,}"', re.I),
     r'"\1": "***REDACTED***"'),
    # Query-string tokens
    (re.compile(r'([?&](token|api_key|key|secret)=)[^\&\s]+', re.I), r'\1***REDACTED***'),
]


class RedactingFilter(logging.Filter):
    """Scrub secrets from every log record before it hits the handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, replacement in _REDACT_PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        record.args = ()  # args already merged into msg
        return True


class DetailedFormatter(logging.Formatter):
    """YYYY-MM-DD HH:MM:SS | LEVEL | filename:func:line | message"""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        record.filename_lineno = f"{record.filename}:{record.funcName}:{record.lineno}"
        return super().format(record)


_DEFAULT_FMT = "%(asctime)s | %(levelname)-8s | %(filename_lineno)-35s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _cleanup_old_logs():
    """Remove .log files older than 7 days in the log directory."""
    if not LOG_DIR.exists():
        return
    import time
    now = time.time()
    cutoff = now - 7 * 86400
    for f in LOG_DIR.glob("smartthings.log*"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def _get_log_level() -> int:
    """Read log level from config; default to INFO."""
    if not CONFIG_FILE.exists():
        return logging.INFO
    try:
        data = json.loads(CONFIG_FILE.read_text())
        level_name = data.get("log_level", "INFO")
        return getattr(logging, level_name.upper(), logging.INFO)
    except Exception:
        return logging.INFO


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Log output goes to ~/.hermes/logs/smartthings.log.
    """
    logger = logging.getLogger(name)
    if getattr(logger, "_st_configured", False):
        return logger

    level = _get_log_level()
    logger.setLevel(level)

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Rotate by size (50 MB) and keep 7 backups
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(DetailedFormatter(_DEFAULT_FMT, _DEFAULT_DATEFMT))

    # Redact sensitive data
    redactor = RedactingFilter()
    handler.addFilter(redactor)
    logger.addFilter(redactor)

    logger.addHandler(handler)

    # Also add a stderr handler
    console = logging.StreamHandler()
    # Console defaults to WARNING to avoid spamming stderr with INFO/DEBUG.
    # If user explicitly sets "console_log_level", respect it.
    console_level = logging.WARNING
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            explicit = data.get("console_log_level")
            if explicit:
                console_level = getattr(logging, explicit.upper(), logging.WARNING)
        except Exception:
            pass
    console.setLevel(console_level)
    console.setFormatter(DetailedFormatter(_DEFAULT_FMT, _DEFAULT_DATEFMT))
    console.addFilter(redactor)
    logger.addHandler(console)

    # Startup cleanup of really old logs
    _cleanup_old_logs()

    logger._st_configured = True  # type: ignore[attr-defined]
    logger.debug("Logger initialized for %s", name)
    return logger
