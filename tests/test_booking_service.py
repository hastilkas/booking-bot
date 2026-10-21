import asyncio
from datetime import date, time

import pytest

from bot.booking_service import SlotTakenError, TooManyBookingsError
from bot.models import Booking

MONDAY = date(2026, 10, 19)  # «сегодня», сейчас 9:00
TUESDAY = date(2026, 10, 20)


def _book(service, user_id=1, day=TUESDAY, start=time(10, 0), master="alex", svc="cut"):
    return service.book(master_id=master, service_id=svc, day=day, start=start,
                        client_name="Иван", phone="+79991234567", user_id=user_id)


async def test_book_and_slot_disappears(service):
    booking = await _book(service)
    assert booking.master == "Алексей" and booking.price == 1800
    slots = await service.free_slots("alex", "cut", TUESDAY)
    assert time(10, 0) not in slots and time(9, 30) not in slots
    # другой мастер этим не затронут
    assert time(12, 0) in await service.free_slots("max", "cut", TUESDAY)


async def test_double_booking_race(service):
    results = await asyncio.gather(_book(service, user_id=1), _book(service, user_id=2), return_exceptions=True)
    assert sum(isinstance(r, Booking) for r in results) == 1
    assert sum(isinstance(r, SlotTakenError) for r in results) == 1


async def test_min_lead_time_today(service):
    slots = await service.free_slots("alex", "cut", MONDAY)
    assert slots[0] == time(10, 0)  # 9:00 + 60 мин запаса
    with pytest.raises(SlotTakenError):
        await _book(service, day=MONDAY, start=time(9, 30))


async def test_limit_per_user(service):
    for hour in (10, 11, 12):
        await _book(service, start=time(hour, 0))
    with pytest.raises(TooManyBookingsError):
        await _book(service, start=time(16, 0))


async def test_cancel_frees_slot_and_checks_owner(service):
    booking = await _book(service)
    assert await service.cancel(booking.id, by_owner=False, user_id=999) is None  # чужая запись
    cancelled = await service.cancel(booking.id, by_owner=False, user_id=1)
    assert cancelled.status == "Отменена клиентом"
    assert time(10, 0) in await service.free_slots("alex", "cut", TUESDAY)
    assert await service.user_bookings(1) == []


async def test_owner_block_all_masters(service):
    await service.storage.add(Booking(day=TUESDAY, start=time(10, 0), duration=240, master="Все", service="Санобработка",
                                      price=0, client_name="", phone="", user_id=0))
    assert time(12, 0) not in await service.free_slots("alex", "cut", TUESDAY)
    assert time(14, 0) in await service.free_slots("max", "cut", TUESDAY)


async def test_days_overview(service):
    overview = await service.days_overview("alex", "cut")
    assert len(overview) == 14
    assert overview[date(2026, 10, 25)] == 0  # воскресенье — выходной
    assert overview[TUESDAY] > 0
