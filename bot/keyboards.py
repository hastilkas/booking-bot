"""Клавиатуры и callback_data.

Каждая кнопка шага несёт в себе весь выбор пользователя (заведение, мастер, услуга, день),
поэтому навигация «Назад» работает без хранения состояния и переживает перезапуск бота.
"""
from __future__ import annotations

from datetime import date, time, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .catalog import Business
from .models import Booking
from .texts import duration_text, hm, short_date


class BizCb(CallbackData, prefix="biz"):
    biz: str


class MenuCb(CallbackData, prefix="menu"):
    biz: str
    action: str  # home | book | my | about | switch


class MasterCb(CallbackData, prefix="m"):
    biz: str
    master: str


class ServiceCb(CallbackData, prefix="s"):
    biz: str
    master: str
    service: str


class DayCb(CallbackData, prefix="d"):
    biz: str
    master: str
    service: str
    day: str  # YYYYMMDD


class TimeCb(CallbackData, prefix="t"):
    biz: str
    master: str
    service: str
    day: str
    time: str  # HHMM


class ConfirmCb(CallbackData, prefix="ok"):
    action: str  # yes | no


class CancelCb(CallbackData, prefix="c"):
    biz: str
    id: str
    step: str  # ask | yes | no


class OwnerCancelCb(CallbackData, prefix="oc"):
    biz: str
    id: str


class OwnerDayCb(CallbackData, prefix="od"):
    day: str


NOOP = "noop"
BTN_CANCEL = "❌ Отменить"


def day_key(d: date) -> str:
    return d.strftime("%Y%m%d")


def time_key(t: time) -> str:
    return t.strftime("%H%M")


def _btn(text: str, cb: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def business_picker(businesses: dict[str, Business]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for biz in businesses.values():
        kb.button(text=biz.title, callback_data=BizCb(biz=biz.id))
    kb.adjust(1)
    return kb.as_markup()


def main_menu(biz: Business, can_switch: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записаться", callback_data=MenuCb(biz=biz.id, action="book"))
    kb.button(text="🗂 Мои записи", callback_data=MenuCb(biz=biz.id, action="my"))
    kb.button(text="ℹ️ О нас и цены", callback_data=MenuCb(biz=biz.id, action="about"))
    if can_switch:
        kb.button(text="🔄 Другое заведение", callback_data=MenuCb(biz=biz.id, action="switch"))
    kb.adjust(1, 2, 1)
    return kb.as_markup()


def back_to_menu(biz: Business) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записаться", callback_data=MenuCb(biz=biz.id, action="book"))
    kb.button(text="🏠 Меню", callback_data=MenuCb(biz=biz.id, action="home"))
    return kb.as_markup()


def after_booking(biz: Business) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗂 Мои записи", callback_data=MenuCb(biz=biz.id, action="my"))
    kb.button(text="🏠 Меню", callback_data=MenuCb(biz=biz.id, action="home"))
    return kb.as_markup()


def masters(biz: Business) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for m in biz.masters.values():
        kb.button(text=m.name, callback_data=MasterCb(biz=biz.id, master=m.id))
    kb.adjust(2)
    kb.row(_btn("⬅️ Назад", MenuCb(biz=biz.id, action="home")))
    return kb.as_markup()


def services(biz: Business, master_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in biz.services_of(master_id):
        kb.button(
            text=f"{s.title} · {biz.format_price(s.price)} · {duration_text(s.duration)}",
            callback_data=ServiceCb(biz=biz.id, master=master_id, service=s.id),
        )
    kb.button(text="⬅️ К мастерам", callback_data=MenuCb(biz=biz.id, action="book"))
    kb.adjust(1)
    return kb.as_markup()


def days(biz: Business, master_id: str, service_id: str, overview: dict[date, int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, (d, free) in enumerate(overview.items()):
        label = ("Сегодня", "Завтра")[i] if i < 2 else short_date(d)
        if free:
            kb.button(
                text=label,
                callback_data=DayCb(biz=biz.id, master=master_id, service=service_id, day=day_key(d)),
            )
        else:
            kb.button(text=f"· {label} ·", callback_data=NOOP)
    kb.adjust(3)
    kb.row(_btn("⬅️ К услугам", MasterCb(biz=biz.id, master=master_id)))
    return kb.as_markup()


def times(biz: Business, master_id: str, service_id: str, d: date, slots: list[time]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(
            text=hm(t),
            callback_data=TimeCb(biz=biz.id, master=master_id, service=service_id, day=day_key(d), time=time_key(t)),
        )
    kb.adjust(4)
    kb.row(_btn("⬅️ К датам", ServiceCb(biz=biz.id, master=master_id, service=service_id)))
    return kb.as_markup()


def confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить запись", callback_data=ConfirmCb(action="yes"))
    kb.button(text="❌ Отмена", callback_data=ConfirmCb(action="no"))
    kb.adjust(1)
    return kb.as_markup()


def my_bookings(biz: Business, bookings: list[Booking]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(
            text=f"❌ Отменить {short_date(b.day)} {hm(b.start)}",
            callback_data=CancelCb(biz=biz.id, id=b.id, step="ask"),
        )
    kb.button(text="📅 Новая запись", callback_data=MenuCb(biz=biz.id, action="book"))
    kb.button(text="🏠 Меню", callback_data=MenuCb(biz=biz.id, action="home"))
    kb.adjust(*([1] * len(bookings)), 2)
    return kb.as_markup()


def cancel_confirm(biz: Business, booking_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, отменить", callback_data=CancelCb(biz=biz.id, id=booking_id, step="yes"))
    kb.button(text="Нет, оставить", callback_data=CancelCb(biz=biz.id, id=booking_id, step="no"))
    return kb.as_markup()


def owner_alert(biz: Business, booking_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить запись", callback_data=OwnerCancelCb(biz=biz.id, id=booking_id))
    return kb.as_markup()


def owner_days(d: date) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️", callback_data=OwnerDayCb(day=day_key(d - timedelta(days=1))))
    kb.button(text="🔄", callback_data=OwnerDayCb(day=day_key(d)))
    kb.button(text="▶️", callback_data=OwnerDayCb(day=day_key(d + timedelta(days=1))))
    return kb.as_markup()


def ask_name(first_name: str | None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=first_name)]] if first_name else []
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True,
                               input_field_placeholder="Ваше имя")


def ask_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+7 999 123-45-67",
    )
