"""Хранилище в Google Таблице. Каждое заведение — отдельный лист.

gspread синхронный, поэтому все вызовы уходят в отдельный поток (asyncio.to_thread),
а чтения кэшируются на несколько секунд, чтобы не упираться в лимиты Google API
(60 запросов в минуту на пользователя).
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
from pathlib import Path

import gspread
from gspread.utils import ValueInputOption

from ..models import Booking
from .base import HEADERS, STATUS_COL, booking_to_row, row_to_booking

log = logging.getLogger(__name__)


class SheetsStorage:
    def __init__(
        self,
        client: gspread.Client,
        spreadsheet_id: str,
        worksheet_title: str,
        cache_ttl: float = 10.0,
    ) -> None:
        self._client = client
        self._spreadsheet_id = spreadsheet_id
        self._title = worksheet_title
        self._ttl = cache_ttl
        self._ws: gspread.Worksheet | None = None
        self._cache: list[list[str]] | None = None
        self._cache_at = 0.0
        self._lock = asyncio.Lock()

    @staticmethod
    def make_client(credentials_file: Path) -> gspread.Client:
        return gspread.service_account(filename=str(credentials_file))

    def _worksheet(self) -> gspread.Worksheet:
        if self._ws is None:
            spreadsheet = self._client.open_by_key(self._spreadsheet_id)
            try:
                self._ws = spreadsheet.worksheet(self._title)
            except gspread.WorksheetNotFound:
                log.info("Создаю лист %r в таблице", self._title)
                ws = spreadsheet.add_worksheet(self._title, rows=1000, cols=len(HEADERS))
                ws.update([HEADERS], "A1", value_input_option=ValueInputOption.raw)
                ws.format("A1:M1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 1}})
                ws.freeze(rows=1)
                self._ws = ws
        return self._ws

    def _rows_sync(self) -> list[list[str]]:
        values = self._worksheet().get_all_values()
        return values[1:]  # без заголовка

    async def _rows(self, fresh: bool = False) -> list[list[str]]:
        if fresh or self._cache is None or _time.monotonic() - self._cache_at > self._ttl:
            self._cache = await asyncio.to_thread(self._rows_sync)
            self._cache_at = _time.monotonic()
        return self._cache

    async def all(self) -> list[Booking]:
        return [b for b in map(row_to_booking, await self._rows()) if b]

    async def add(self, booking: Booking) -> None:
        async with self._lock:
            row = booking_to_row(booking)
            await asyncio.to_thread(
                lambda: self._worksheet().append_row(
                    row, value_input_option=ValueInputOption.raw, table_range="A1"
                )
            )
            self._cache = None

    async def update_status(self, booking_id: str, status: str) -> Booking | None:
        async with self._lock:
            rows = await self._rows(fresh=True)
            for index, row in enumerate(rows):
                if row and row[0] == booking_id:
                    sheet_row = index + 2  # +1 за заголовок, +1 т.к. нумерация с 1
                    await asyncio.to_thread(self._worksheet().update_cell, sheet_row, STATUS_COL, status)
                    self._cache = None
                    updated = list(row) + [""] * (len(HEADERS) - len(row))
                    updated[STATUS_COL - 1] = status
                    return row_to_booking(updated)
            return None
