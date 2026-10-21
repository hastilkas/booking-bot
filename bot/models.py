from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

STATUS_ACTIVE = "Активна"
STATUS_CANCELLED_CLIENT = "Отменена клиентом"
STATUS_CANCELLED_OWNER = "Отменена администратором"

_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без похожих O/0, I/1


def new_booking_id() -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))


@dataclass
class Booking:
    day: date
    start: time
    duration: int
    master: str  # имя мастера — так владельцу удобнее читать и править таблицу руками
    service: str
    price: int
    client_name: str
    phone: str
    user_id: int
    username: str = ""
    status: str = STATUS_ACTIVE
    id: str = field(default_factory=new_booking_id)
    created_at: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))

    @property
    def start_dt(self) -> datetime:
        return datetime.combine(self.day, self.start)

    @property
    def end_dt(self) -> datetime:
        return self.start_dt + timedelta(minutes=self.duration)

    @property
    def is_active(self) -> bool:
        # всё, что владелец не пометил как «Отменена…», считается занятым временем
        return not self.status.strip().lower().startswith("отмен")
