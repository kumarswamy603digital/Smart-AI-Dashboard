"""Central application settings loaded from environment variables (.env supported).

Every tunable value lives here so no other module hardcodes paths, keys,
model names or limits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # --- Paths -------------------------------------------------------------
    base_dir: Path = BASE_DIR
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    reports_dir: Path = field(default_factory=lambda: BASE_DIR / "reports")
    sample_csv: Path = field(default_factory=lambda: BASE_DIR / "data" / "sample_sales.csv")

    # --- Server ------------------------------------------------------------
    host: str = field(default_factory=lambda: os.getenv("DASH_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int_env("DASH_PORT", 8050))
    debug: bool = field(default_factory=lambda: os.getenv("DASH_DEBUG", "false").lower() == "true")

    # --- Upload limits -------------------------------------------------------
    max_upload_bytes: int = field(default_factory=lambda: _int_env("MAX_UPLOAD_MB", 15) * 1_024_024)
    max_rows: int = field(default_factory=lambda: _int_env("MAX_ROWS", 200_000))
    max_columns: int = field(default_factory=lambda: _int_env("MAX_COLUMNS", 200))
    max_upload_mb_display: int = field(default_factory=lambda: _int_env("MAX_UPLOAD_MB", 15))

    # --- OpenAI --------------------------------------------------------------
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip())
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    )
    openai_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("OPENAI_TIMEOUT", "30")))
    openai_max_context_chars: int = field(default_factory=lambda: _int_env("OPENAI_MAX_CONTEXT_CHARS", 6000))
    openai_max_history_turns: int = field(default_factory=lambda: _int_env("OPENAI_MAX_HISTORY_TURNS", 6))

    # --- Analytics -------------------------------------------------------------
    session_store_capacity: int = field(default_factory=lambda: _int_env("SESSION_STORE_CAPACITY", 64))
    top_n_default: int = 10
    table_preview_rows: int = 25

    @property
    def ai_configured(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
settings.reports_dir.mkdir(parents=True, exist_ok=True)
