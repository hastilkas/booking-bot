"""SheetsStorage на фейковом gspread-клиенте: проверяем формат листа и операции без сети."""
from datetime import date, time

import gspread

from bot.models import Booking
from bot.storage.base import HEADERS
from bot.storage.sheets import SheetsStorage


class FakeWorksheet:
    def __init__(self):
        self.rows: list[list[str]] = []

    def update(self, values, range_name, value_input_option=None):
        self.rows[0:1] = values

    def format(self, *a, **kw): pass
    def freeze(self, *a, **kw): pass

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def append_row(self, row, value_input_option=None, table_range=None):
        assert value_input_option == "RAW"  # иначе Sheets превратит телефон и дату в числа
        self.rows.append(list(row))

    def update_cell(self, row, col, value):
        self.rows[row - 1][col - 1] = value


class FakeSpreadsheet:
    def __init__(self):
        self.sheets = {}

    def worksheet(self, title):
        if title not in self.sheets:
            raise gspread.WorksheetNotFound(title)
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        self.sheets[title] = FakeWorksheet()
        return self.sheets[title]


class FakeClient:
    def __init__(self):
        self.spreadsheet = FakeSpreadsheet()

    def open_by_key(self, key):
        return self.spreadsheet


async def test_sheets_storage_flow():
    client = FakeClient()
    storage = SheetsStorage(client, "sheet-id", "Old Fox Barbershop", cache_ttl=0)
    booking = Booking(day=date(2026, 10, 20), start=time(10, 0), duration=60, master="Алексей", service="Стрижка",
                      price=1800, client_name="Иван", phone="+79991234567", user_id=1)

    await storage.add(booking)
    ws = client.spreadsheet.sheets["Old Fox Barbershop"]
    assert ws.rows[0] == HEADERS
    assert ws.rows[1][2:4] == ["20.10.2026", "10:00"] and ws.rows[1][9] == "+79991234567"

    [loaded] = await storage.all()
    assert loaded.id == booking.id and loaded.is_active

    updated = await storage.update_status(booking.id, "Отменена клиентом")
    assert not updated.is_active and ws.rows[1][12] == "Отменена клиентом"
    assert await storage.update_status("NOPE", "x") is None
