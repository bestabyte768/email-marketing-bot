"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "email_bot.db"
DEFAULT_CSV = BASE_DIR / "profiles.csv"


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key, default) or default).strip().strip('"').strip("'")


@dataclass
class Settings:
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    daily_limit: int = 50
    delay_min_minutes: int = 20
    delay_max_minutes: int = 30
    min_age: int = 28
    max_age: int = 45


def load_settings() -> Settings:
    """Always re-read .env so App Password changes take effect without full redeploy."""
    load_dotenv(BASE_DIR / ".env", override=True)
    return Settings(
        smtp_host=_env("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(_env("SMTP_PORT", "587") or "587"),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD").replace(" ", ""),
        smtp_from=_env("SMTP_FROM"),
        smtp_use_tls=_env("SMTP_USE_TLS", "true").lower() == "true",
        daily_limit=int(_env("DAILY_LIMIT", "50") or "50"),
        delay_min_minutes=int(_env("DELAY_MIN_MINUTES", "20") or "20"),
        delay_max_minutes=int(_env("DELAY_MAX_MINUTES", "30") or "30"),
        min_age=int(_env("MIN_AGE", "28") or "28"),
        max_age=int(_env("MAX_AGE", "45") or "45"),
    )


settings = load_settings()


def refresh_settings() -> Settings:
    global settings
    settings = load_settings()
    return settings
