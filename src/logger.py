"""Central logging configuration for datta.ai."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import settings


LOGGER_NAME = "datta.ai"
_CONFIGURED = False


class SecretRedactionFilter(logging.Filter):
    """Prevent common API-key formats from being written to logs."""

    PATTERNS = (
        re.compile(r"gsk_[A-Za-z0-9_-]+"),
        re.compile(r"sk-[A-Za-z0-9_-]+"),
        re.compile(r"AIza[0-9A-Za-z_-]+"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        for pattern in self.PATTERNS:
            message = pattern.sub("[REDACTED]", message)

        record.msg = message
        record.args = ()

        return True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured datta.ai logger."""

    global _CONFIGURED

    root_logger = logging.getLogger(LOGGER_NAME)

    if not _CONFIGURED:
        root_logger.setLevel(
            getattr(logging, settings.log_level, logging.INFO)
        )
        root_logger.propagate = False

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        redaction = SecretRedactionFilter()

        settings.log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )

        file_handler.setFormatter(formatter)
        file_handler.addFilter(redaction)

        root_logger.addHandler(file_handler)

        if settings.debug or settings.environment != "production":
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.addFilter(redaction)

            root_logger.addHandler(console_handler)

        _CONFIGURED = True

    return (
        root_logger
        if not name
        else logging.getLogger(f"{LOGGER_NAME}.{name}")
    )


logger = get_logger()