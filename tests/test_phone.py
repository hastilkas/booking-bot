import pytest

from bot.phone import normalize_phone, pretty_phone


@pytest.mark.parametrize("raw", ["+7 999 123-45-67", "89991234567", "8 (999) 123 45 67", "9991234567", "+7(999)1234567"])
def test_valid_ru(raw):
    assert normalize_phone(raw) == "+79991234567"


@pytest.mark.parametrize("raw", ["", "123", "привет", "+7 999 123", "8999123456789999", "+1 000 000 0000"])
def test_invalid(raw):
    assert normalize_phone(raw) is None


def test_foreign_and_pretty():
    assert normalize_phone("+375 29 123-45-67") == "+375291234567"
    assert pretty_phone("+79991234567") == "+7 999 123-45-67"
