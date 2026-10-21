"""Расчёт свободных окон. Чистые функции без I/O — легко тестировать."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from .catalog import Master

Interval = tuple[datetime, datetime]


def overlaps(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def free_slots(
    master: Master,
    day: date,
    duration: int,
    busy: Iterable[Interval],
    step: int,
    earliest: datetime,
) -> list[time]:
    """Возвращает время начала всех окон, куда помещается услуга длительностью `duration`.

    busy     — уже занятые интервалы мастера (записи), перерывы мастера учитываются здесь же;
    earliest — раньше этого момента записаться нельзя (сейчас + минимальный запас).
    """
    hours = master.hours_on(day)
    if hours is None:
        return []

    blocked = list(busy)
    blocked += [(datetime.combine(day, a), datetime.combine(day, b)) for a, b in master.breaks]

    shift_start = datetime.combine(day, hours[0])
    shift_end = datetime.combine(day, hours[1])
    length = timedelta(minutes=duration)

    result: list[time] = []
    start = shift_start
    while start + length <= shift_end:
        candidate = (start, start + length)
        if start >= earliest and not any(overlaps(candidate, b) for b in blocked):
            result.append(start.time())
        start += timedelta(minutes=step)
    return result
