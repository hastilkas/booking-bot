"""Валидация и нормализация телефонных номеров (на базе libphonenumber)."""
from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


def normalize_phone(raw: str, region: str = "RU") -> str | None:
    """Приводит номер к формату E.164 (+79991234567) или возвращает None, если номер невалиден.

    Понимает «8 999 123-45-67», «+7(999)1234567», «9991234567» и номера других стран с «+».
    """
    text = (raw or "").strip()
    if not text or len(text) > 32:
        return None
    # Российская привычка писать 8 вместо +7
    if region == "RU" and text.startswith("8") and len("".join(ch for ch in text if ch.isdigit())) == 11:
        text = "+7" + text[1:]
    try:
        number = phonenumbers.parse(text, region)
    except NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def pretty_phone(e164: str) -> str:
    try:
        return phonenumbers.format_number(phonenumbers.parse(e164, None), PhoneNumberFormat.INTERNATIONAL)
    except NumberParseException:
        return e164
