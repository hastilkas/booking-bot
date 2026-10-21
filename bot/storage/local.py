"""Локальное хранилище в JSON-файле — для разработки и демо без Google-аккаунта."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import Booking
from .base import booking_to_row, row_to_booking


class LocalStorage:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read_rows(self) -> list[list[str]]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write_rows(self, rows: list[list[str]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._path)  # атомарная замена — файл не побьётся при падении

    async def all(self) -> list[Booking]:
        return [b for b in map(row_to_booking, self._read_rows()) if b]

    async def add(self, booking: Booking) -> None:
        rows = self._read_rows()
        rows.append(booking_to_row(booking))
        self._write_rows(rows)

    async def update_status(self, booking_id: str, status: str) -> Booking | None:
        rows = self._read_rows()
        for row in rows:
            if row and row[0] == booking_id:
                row[12] = status
                self._write_rows(rows)
                return row_to_booking(row)
        return None
