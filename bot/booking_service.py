"""Бизнес-логика записи: свободные дни/окна, создание и отмена записей."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .catalog import Business, Master
from .models import STATUS_CANCELLED_CLIENT, STATUS_CANCELLED_OWNER, Booking
from .slots import Interval, free_slots
from .storage import BookingStorage

# Если владелец вписал в колонку «Мастер» одно из этих слов, время блокируется у всех мастеров
ALL_MASTERS = {"все", "*", "салон закрыт"}


class BookingError(Exception):
    """Ошибка, которую можно показать пользователю как есть."""


class SlotTakenError(BookingError):
    pass


class TooManyBookingsError(BookingError):
    pass


class BookingService:
    def __init__(
        self,
        business: Business,
        storage: BookingStorage,
        tz: ZoneInfo,
        days_ahead: int = 14,
        min_lead_minutes: int = 60,
        max_active_per_user: int = 3,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.business = business
        self.storage = storage
        self.tz = tz
        self.days_ahead = days_ahead
        self.min_lead = timedelta(minutes=min_lead_minutes)
        self.max_active_per_user = max_active_per_user
        self._clock = clock or (lambda: datetime.now(tz))
        # Защищает от гонки «два клиента нажали на одно окно одновременно»
        self._lock = asyncio.Lock()

    # --- время -------------------------------------------------------------
    def now(self) -> datetime:
        """Текущее локальное время заведения (naive — все даты в таблице тоже локальные)."""
        return self._clock().astimezone(self.tz).replace(tzinfo=None, microsecond=0)

    def booking_days(self) -> list[date]:
        today = self.now().date()
        return [today + timedelta(days=i) for i in range(self.days_ahead)]

    # --- расчёт окон -------------------------------------------------------
    @staticmethod
    def _blocks_master(booking: Booking, master: Master) -> bool:
        name = booking.master.strip().lower()
        return name == master.name.strip().lower() or name in ALL_MASTERS

    def _busy(self, bookings: list[Booking], master: Master, day: date) -> list[Interval]:
        return [
            (b.start_dt, b.end_dt)
            for b in bookings
            if b.is_active and b.day == day and self._blocks_master(b, master)
        ]

    def _slots(self, bookings: list[Booking], master_id: str, service_id: str, day: date) -> list[time]:
        master = self.business.masters[master_id]
        service = self.business.services[service_id]
        if day not in self.booking_days():
            return []
        return free_slots(
            master,
            day,
            service.duration,
            self._busy(bookings, master, day),
            self.business.slot_step,
            earliest=self.now() + self.min_lead,
        )

    async def free_slots(self, master_id: str, service_id: str, day: date) -> list[time]:
        return self._slots(await self.storage.all(), master_id, service_id, day)

    async def days_overview(self, master_id: str, service_id: str) -> dict[date, int]:
        """Количество свободных окон по каждому дню горизонта записи (один запрос к хранилищу)."""
        bookings = await self.storage.all()
        return {day: len(self._slots(bookings, master_id, service_id, day)) for day in self.booking_days()}

    # --- записи ------------------------------------------------------------
    async def user_bookings(self, user_id: int) -> list[Booking]:
        now = self.now()
        items = [b for b in await self.storage.all() if b.user_id == user_id and b.is_active and b.end_dt > now]
        return sorted(items, key=lambda b: b.start_dt)

    async def bookings_on(self, day: date) -> list[Booking]:
        items = [b for b in await self.storage.all() if b.day == day and b.is_active]
        return sorted(items, key=lambda b: (b.start, b.master))

    async def get(self, booking_id: str) -> Booking | None:
        return next((b for b in await self.storage.all() if b.id == booking_id), None)

    async def book(
        self,
        *,
        master_id: str,
        service_id: str,
        day: date,
        start: time,
        client_name: str,
        phone: str,
        user_id: int,
        username: str = "",
    ) -> Booking:
        master = self.business.masters[master_id]
        service = self.business.services[service_id]
        async with self._lock:
            bookings = await self.storage.all()
            now = self.now()
            active = [b for b in bookings if b.user_id == user_id and b.is_active and b.end_dt > now]
            if len(active) >= self.max_active_per_user:
                raise TooManyBookingsError(
                    f"У вас уже {len(active)} активных записи. Отмените одну из них в «Мои записи», чтобы записаться снова."
                )
            # Перепроверяем окно прямо перед записью: его могли занять, пока клиент вводил телефон
            if start not in self._slots(bookings, master_id, service_id, day):
                raise SlotTakenError("Упс, это время только что заняли. Выберите, пожалуйста, другое окно 👇")
            booking = Booking(
                day=day,
                start=start,
                duration=service.duration,
                master=master.name,
                service=service.title,
                price=service.price,
                client_name=client_name,
                phone=phone,
                user_id=user_id,
                username=username,
                created_at=now,
            )
            await self.storage.add(booking)
            return booking

    async def cancel(self, booking_id: str, *, by_owner: bool, user_id: int | None = None) -> Booking | None:
        booking = await self.get(booking_id)
        if booking is None or not booking.is_active:
            return None
        if not by_owner and booking.user_id != user_id:
            return None
        status = STATUS_CANCELLED_OWNER if by_owner else STATUS_CANCELLED_CLIENT
        return await self.storage.update_status(booking_id, status)
