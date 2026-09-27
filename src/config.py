"""Central application configuration for datta.ai.

All environment-driven settings are loaded here so the rest of the
application does not need to read environment variables directly.
Supports both local .env configuration and Streamlit Cloud secrets.
"""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# Project Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# ============================================================
# Secret / Environment Helpers
# ============================================================

def _get_value(name: str, default: str = "") -> str:
    """Read a setting from environment variables or Streamlit secrets."""

    value = os.getenv(name)

    if value is not None:
        return value.strip()

    try:
        import streamlit as st

        value = st.secrets.get(name, default)

        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


def _get_int(name: str, default: int) -> int:
    """Read an integer setting."""

    value = _get_value(name, str(default))

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer, got: {value!r}"
        ) from exc


def _get_float(name: str, default: float) -> float:
    """Read a floating-point setting."""

    value = _get_value(name, str(default))

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number, got: {value!r}"
        ) from exc


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean setting."""

    value = _get_value(
        name,
        str(default),
    ).lower()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be a boolean, got: {value!r}"
    )


def _resolve_path(value: str) -> Path:
    """Resolve a path relative to the project root when necessary."""

    path = Path(value).expanduser()

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


# ============================================================
# Settings
# ============================================================

@dataclass(frozen=True)
class Settings:
    """Runtime settings for datta.ai."""

    environment: str
    debug: bool
    log_level: str

    groq_api_key: str
    groq_model: str
    groq_temperature: float

    search_max_results: int
    max_research_rounds: int

    database_path: Path

    log_file: Path
    log_max_bytes: int
    log_backup_count: int


# ============================================================
# Load Settings
# ============================================================

settings = Settings(
    environment=_get_value(
        "APP_ENV",
        "development",
    ).lower(),

    debug=_get_bool(
        "DEBUG",
        False,
    ),

    log_level=_get_value(
        "LOG_LEVEL",
        "INFO",
    ).upper(),

    groq_api_key=_get_value(
        "GROQ_API_KEY",
        "",
    ),

    groq_model=_get_value(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    ),

    groq_temperature=_get_float(
        "GROQ_TEMPERATURE",
        0.0,
    ),

    search_max_results=_get_int(
        "SEARCH_MAX_RESULTS",
        8,
    ),

    max_research_rounds=_get_int(
        "MAX_RESEARCH_ROUNDS",
        1,
    ),

    database_path=_resolve_path(
        _get_value(
            "DATABASE_PATH",
            "data/datta_ai.db",
        )
    ),

    log_file=_resolve_path(
        _get_value(
            "LOG_FILE",
            "logs/datta_ai.log",
        )
    ),

    log_max_bytes=_get_int(
        "LOG_MAX_BYTES",
        5 * 1024 * 1024,
    ),

    log_backup_count=_get_int(
        "LOG_BACKUP_COUNT",
        3,
    ),
)


# ============================================================
# Configuration Validation
# ============================================================

if not settings.environment:
    raise ValueError(
        "APP_ENV cannot be empty."
    )


if not settings.log_level:
    raise ValueError(
        "LOG_LEVEL cannot be empty."
    )


if not settings.groq_api_key:
    raise ValueError(
        "GROQ_API_KEY is not configured."
    )


if settings.groq_api_key.lower().startswith("your_"):
    raise ValueError(
        "GROQ_API_KEY still contains the placeholder value."
    )


if settings.search_max_results < 1:
    raise ValueError(
        "SEARCH_MAX_RESULTS must be at least 1."
    )


if settings.max_research_rounds < 1:
    raise ValueError(
        "MAX_RESEARCH_ROUNDS must be at least 1."
    )


if settings.groq_temperature < 0:
    raise ValueError(
        "GROQ_TEMPERATURE cannot be negative."
    )


if settings.log_max_bytes < 1024:
    raise ValueError(
        "LOG_MAX_BYTES must be at least 1024 bytes."
    )


if settings.log_backup_count < 0:
    raise ValueError(
        "LOG_BACKUP_COUNT cannot be negative."
    )


# ============================================================
# Required Directories
# ============================================================

settings.database_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

settings.log_file.parent.mkdir(
    parents=True,
    exist_ok=True,
)