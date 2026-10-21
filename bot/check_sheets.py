"""Проверка подключения к Google Таблице: python -m bot.check_sheets"""
from __future__ import annotations

import json
import os
import sys

import gspread
from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError

from .config import ROOT_DIR, _path


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    credentials = _path(os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"))
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()

    if not credentials.exists():
        print(f"❌ Нет файла ключа: {credentials}\n   Скачайте JSON-ключ сервисного аккаунта и положите его сюда.")
        return 1
    email = json.loads(credentials.read_text(encoding="utf-8")).get("client_email", "?")
    print(f"🔑 Сервисный аккаунт: {email}")

    if not spreadsheet_id:
        print("❌ SPREADSHEET_ID пуст в .env")
        return 1
    try:
        spreadsheet = gspread.service_account(filename=str(credentials)).open_by_key(spreadsheet_id)
    except gspread.SpreadsheetNotFound:
        print(f"❌ Таблица не найдена. Проверьте ID и откройте доступ «Редактор» для {email}")
        return 1
    except gspread.exceptions.APIError as exc:
        print(f"❌ Google API вернул ошибку: {exc}\n   Убедитесь, что включён Google Sheets API в вашем проекте Google Cloud.")
        return 1
    except GoogleAuthError as exc:
        print(f"❌ Ключ не подошёл: {exc}")
        return 1

    print(f"✅ Доступ есть: «{spreadsheet.title}», листы: {[ws.title for ws in spreadsheet.worksheets()]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
