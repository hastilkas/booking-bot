"""Настройки бота из переменных окружения (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_ids: frozenset[int]
    presets: tuple[str, ...]
    presets_dir: Path
    tz: ZoneInfo
    storage: str  # "local" | "sheets"
    data_dir: Path
    google_credentials_file: Path
    spreadsheet_id: str
    days_ahead: int
    min_lead_minutes: int
    max_active_per_user: int
    phone_region: str
    demo_mode: bool


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "да"}


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    env = os.environ.get

    token = env("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("BOT_TOKEN не задан. Скопируйте .env.example в .env и вставьте токен от @BotFather.")

    try:
        owner_ids = frozenset(int(x) for x in env("OWNER_IDS", "").replace(" ", "").split(",") if x)
    except ValueError as exc:
        raise ConfigError("OWNER_IDS должен быть списком числовых Telegram ID через запятую") from exc

    presets = tuple(p.strip() for p in env("PRESETS", "barbershop").split(",") if p.strip())
    if not presets:
        raise ConfigError("PRESETS пуст — укажите хотя бы один пресет, например barbershop")

    storage = env("STORAGE", "local").strip().lower()
    if storage not in {"local", "sheets"}:
        raise ConfigError("STORAGE должен быть local или sheets")

    spreadsheet_id = env("SPREADSHEET_ID", "").strip()
    credentials = _path(env("GOOGLE_CREDENTIALS_FILE", "credentials.json"))
    if storage == "sheets":
        if not spreadsheet_id:
            raise ConfigError("Для STORAGE=sheets нужен SPREADSHEET_ID (ID из ссылки на таблицу)")
        if not credentials.exists():
            raise ConfigError(f"Файл сервисного аккаунта не найден: {credentials}")

    return Settings(
        bot_token=token,
        owner_ids=owner_ids,
        presets=presets,
        presets_dir=_path(env("PRESETS_DIR", "presets")),
        tz=ZoneInfo(env("TIMEZONE", "Europe/Moscow")),
        storage=storage,
        data_dir=_path(env("DATA_DIR", "data")),
        google_credentials_file=credentials,
        spreadsheet_id=spreadsheet_id,
        days_ahead=int(env("BOOKING_DAYS_AHEAD", "14")),
        min_lead_minutes=int(env("MIN_LEAD_MINUTES", "60")),
        max_active_per_user=int(env("MAX_ACTIVE_PER_USER", "3")),
        phone_region=env("PHONE_REGION", "RU").upper(),
        demo_mode=_bool(env("DEMO_MODE", "false")),
    )
