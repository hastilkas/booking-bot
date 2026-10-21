import json
from datetime import date, datetime, time

import pytest

from bot.catalog import CatalogError, parse_business
from bot.keyboards import TimeCb
from bot.models import Booking
from bot.storage.base import booking_to_row, row_to_booking


def test_all_presets_valid(businesses):
    assert set(businesses) == {"barbershop", "tattoo", "autoservice", "nails"}
    for biz in businesses.values():
        for master in biz.masters.values():
            assert master.schedule, f"{biz.id}.{master.id} без графика"


def test_callback_data_fits_telegram_limit(businesses):
    for biz in businesses.values():
        for m in biz.masters.values():
            for s in m.service_ids:
                packed = TimeCb(biz=biz.id, master=m.id, service=s, day="20261231", time="2330").pack()
                assert len(packed.encode()) <= 64


def test_unknown_service_rejected(businesses):
    raw = {"id": "x", "name": "X", "services": [{"id": "a", "title": "A", "duration": 30}],
           "masters": [{"id": "m", "name": "M", "services": ["nope"], "schedule": {}}]}
    with pytest.raises(CatalogError):
        parse_business(raw)


def test_row_roundtrip():
    b = Booking(day=date(2026, 10, 20), start=time(14, 30), duration=90, master="Алексей", service="Стрижка",
                price=1800, client_name="Иван", phone="+79991234567", user_id=42, username="ivan",
                created_at=datetime(2026, 10, 18, 12, 5))
    assert row_to_booking(booking_to_row(b)) == b


def test_manual_owner_row_is_parsed():
    # владелец вписал в таблицу только самое нужное, чтобы закрыть время
    b = row_to_booking(["", "", "20.10.2026", "9:00", "", "Все"])
    assert b.day == date(2026, 10, 20) and b.start == time(9, 0) and b.duration == 60 and b.is_active
    assert row_to_booking(["", "", "не дата", "9:00"]) is None
