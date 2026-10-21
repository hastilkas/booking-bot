from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bot.booking_service import BookingService
from bot.catalog import load_businesses
from bot.storage import LocalStorage

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Europe/Moscow")
# Понедельник, 9:00 — у Алексея (barbershop) смена 10:00–20:00 с перерывом 14:00–15:00
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=TZ)


@pytest.fixture
def businesses():
    return load_businesses(ROOT / "presets", ("barbershop", "tattoo", "autoservice", "nails"))


@pytest.fixture
def barbershop(businesses):
    return businesses["barbershop"]


@pytest.fixture
def service(barbershop, tmp_path):
    return BookingService(barbershop, LocalStorage(tmp_path / "b.json"), TZ, days_ahead=14,
                          min_lead_minutes=60, max_active_per_user=3, clock=lambda: NOW)
