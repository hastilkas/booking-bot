from __future__ import annotations

from ..catalog import Business
from ..config import Settings
from .base import BookingStorage
from .local import LocalStorage


def build_storages(settings: Settings, businesses: dict[str, Business]) -> dict[str, BookingStorage]:
    if settings.storage == "sheets":
        from .sheets import SheetsStorage

        client = SheetsStorage.make_client(settings.google_credentials_file)
        return {
            biz_id: SheetsStorage(client, settings.spreadsheet_id, worksheet_title=biz.name[:90])
            for biz_id, biz in businesses.items()
        }
    return {biz_id: LocalStorage(settings.data_dir / f"bookings_{biz_id}.json") for biz_id in businesses}


__all__ = ["BookingStorage", "LocalStorage", "build_storages"]
