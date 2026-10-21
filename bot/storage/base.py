"""Общий интерфейс хранилища и формат строки таблицы."""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Protocol

from ..models import STATUS_ACTIVE, Booking

log = logging.getLogger(__name__)

# Порядок колонок в Google Таблице (и в локальном JSON — формат один и тот же)
HEADERS = [
    "ID",
    "Создано",
    "Дата",
    "Время",
    "Длительность, мин",
    "Мастер",
    "Услуга",
    "Цена",
    "Клиент",
    "Телефон",
    "Telegram",
    "User ID",
    "Статус",
]
STATUS_COL = HEADERS.index("Статус") + 1  # gspread считает колонки с 1

DATE_FMT = "%d.%m.%Y"
CREATED_FMT = "%d.%m.%Y %H:%M"


class BookingStorage(Protocol):
    async def all(self) -> list[Booking]: ...

    async def add(self, booking: Booking) -> None: ...

    async def update_status(self, booking_id: str, status: str) -> Booking | None: ...


def booking_to_row(b: Booking) -> list[str]:
    return [
        b.id,
        b.created_at.strftime(CREATED_FMT),
        b.day.strftime(DATE_FMT),
        b.start.strftime("%H:%M"),
        str(b.duration),
        b.master,
        b.service,
        str(b.price),
        b.client_name,
        b.phone,
        f"@{b.username}" if b.username else "",
        str(b.user_id),
        b.status,
    ]


def _parse_day(value: str) -> date:
    value = value.strip()
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"bad date {value!r}")


def _int(value: str, default: int = 0) -> int:
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else default


def row_to_booking(row: list[str]) -> Booking | None:
    """Парсит строку таблицы. Строки, добавленные владельцем вручную (например, «блок» времени),
    тоже поддерживаются: обязательны только дата, время и мастер."""
    row = list(row) + [""] * (len(HEADERS) - len(row))
    try:
        created = datetime.strptime(row[1].strip(), CREATED_FMT) if row[1].strip() else datetime.min
        return Booking(
            id=row[0].strip() or "—",
            created_at=created,
            day=_parse_day(row[2]),
            start=time.fromisoformat(row[3].strip().zfill(5)),
            duration=_int(row[4], default=60),
            master=row[5].strip(),
            service=row[6].strip(),
            price=_int(row[7]),
            client_name=row[8].strip(),
            phone=row[9].strip(),
            username=row[10].strip().lstrip("@"),
            user_id=_int(row[11]),
            status=row[12].strip() or STATUS_ACTIVE,
        )
    except ValueError as exc:
        log.warning("Пропускаю строку с ошибкой (%s): %s", exc, row)
        return None
