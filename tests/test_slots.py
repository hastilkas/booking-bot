from datetime import date, datetime, time

from bot.slots import free_slots

MONDAY = date(2026, 10, 19)


def test_shift_with_break(barbershop):
    alex = barbershop.masters["alex"]
    slots = free_slots(alex, MONDAY, 60, [], 30, earliest=datetime(2026, 10, 1))
    assert slots[0] == time(10, 0)
    assert slots[-1] == time(19, 0)  # услуга в 60 мин должна закончиться до 20:00
    # перерыв 14:00–15:00: нельзя начать в 13:30 и 14:00/14:30
    assert time(13, 0) in slots
    assert time(13, 30) not in slots and time(14, 0) not in slots and time(14, 30) not in slots
    assert time(15, 0) in slots


def test_existing_booking_blocks_overlaps(barbershop):
    alex = barbershop.masters["alex"]
    busy = [(datetime(2026, 10, 19, 11, 0), datetime(2026, 10, 19, 12, 30))]
    slots = free_slots(alex, MONDAY, 60, busy, 30, earliest=datetime(2026, 10, 1))
    assert time(10, 0) in slots  # 10:00–11:00 вплотную — можно
    assert time(10, 30) not in slots and time(11, 0) not in slots and time(12, 0) not in slots
    assert time(12, 30) in slots


def test_day_off_and_earliest(barbershop):
    alex = barbershop.masters["alex"]
    assert free_slots(alex, date(2026, 10, 25), 30, [], 30, earliest=datetime(2026, 10, 1)) == []  # воскресенье
    slots = free_slots(alex, MONDAY, 30, [], 30, earliest=datetime(2026, 10, 19, 16, 10))
    assert slots[0] == time(16, 30)
