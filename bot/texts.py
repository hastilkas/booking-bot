"""Тексты сообщений и форматирование. Всё пользовательское экранируется (parse_mode=HTML)."""
from __future__ import annotations

from datetime import date, time
from html import escape

from .catalog import Business, Master, Service
from .models import Booking
from .phone import pretty_phone

WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
WEEKDAYS_FULL = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря")
MONTHS_SHORT = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


def human_date(d: date) -> str:
    return f"{d.day} {MONTHS_GEN[d.month - 1]}, {WEEKDAYS_FULL[d.weekday()]}"


def short_date(d: date) -> str:
    return f"{WEEKDAYS_SHORT[d.weekday()]} {d.day} {MONTHS_SHORT[d.month - 1]}"


def hm(t: time) -> str:
    return t.strftime("%H:%M")


def duration_text(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} ч {m} мин"
    return f"{h} ч" if h else f"{m} мин"


def welcome(biz: Business, first_name: str) -> str:
    lines = [f"Привет, {escape(first_name)}! 👋", "", f"<b>{escape(biz.title)}</b>"]
    if biz.description:
        lines.append(escape(biz.description))
    lines += ["", "Запишитесь онлайн за 30 секунд — без звонков и ожидания ответа."]
    return "\n".join(lines)


def about(biz: Business) -> str:
    lines = [f"<b>{escape(biz.title)}</b>", escape(biz.description), ""]
    if biz.address:
        lines.append(f"📍 {escape(biz.address)}")
    if biz.phone:
        lines.append(f"📞 {escape(biz.phone)}")
    lines += ["", "<b>Мастера:</b>"]
    lines += [f"• {escape(m.name)} — {escape(m.about)}" for m in biz.masters.values()]
    lines += ["", "<b>Услуги и цены:</b>"]
    lines += [
        f"• {escape(s.title)} — {biz.format_price(s.price)} ({duration_text(s.duration)})"
        for s in biz.services.values()
    ]
    return "\n".join(lines)


def choose_master(biz: Business) -> str:
    lines = ["<b>Шаг 1 из 4.</b> Выберите мастера:", ""]
    lines += [f"<b>{escape(m.name)}</b> — {escape(m.about)}" for m in biz.masters.values()]
    return "\n".join(lines)


def choose_service(master: Master) -> str:
    return f"<b>Шаг 2 из 4.</b> Мастер: <b>{escape(master.name)}</b>\nВыберите услугу:"


def choose_day(master: Master, service: Service, has_days: bool) -> str:
    text = (
        f"<b>Шаг 3 из 4.</b> {escape(master.name)} · {escape(service.title)}\n"
        f"Выберите день (длительность — {duration_text(service.duration)}):"
    )
    if not has_days:
        text += "\n\n😔 В ближайшие дни свободных окон нет. Попробуйте другого мастера."
    return text


def choose_time(master: Master, service: Service, day: date) -> str:
    return (
        f"<b>Шаг 4 из 4.</b> {escape(master.name)} · {escape(service.title)}\n"
        f"📅 {human_date(day)}\nВыберите удобное время:"
    )


def booking_card(biz: Business, master: str, service: Service | str, price: int, day: date, start: time,
                 client_name: str = "", phone: str = "") -> str:
    service_title = service.title if isinstance(service, Service) else service
    lines = [
        f"🏠 {escape(biz.title)}",
        f"👤 Мастер: <b>{escape(master)}</b>",
        f"🧾 Услуга: <b>{escape(service_title)}</b>",
        f"📅 Дата: <b>{human_date(day)}</b>",
        f"🕐 Время: <b>{hm(start)}</b>",
        f"💳 Стоимость: <b>{biz.format_price(price)}</b>",
    ]
    if client_name:
        lines.append(f"🙋 Имя: <b>{escape(client_name)}</b>")
    if phone:
        lines.append(f"📱 Телефон: <b>{escape(pretty_phone(phone))}</b>")
    return "\n".join(lines)


def booking_confirmed(biz: Business, b: Booking) -> str:
    card = booking_card(biz, b.master, b.service, b.price, b.day, b.start, b.client_name, b.phone)
    footer = f"\n\n📍 {escape(biz.address)}" if biz.address else ""
    return f"✅ <b>Вы записаны!</b> Номер записи: <code>{b.id}</code>\n\n{card}{footer}\n\nЕсли планы изменятся — отмените запись в «Мои записи»."


def owner_alert(biz: Business, b: Booking) -> str:
    contact = f'<a href="tg://user?id={b.user_id}">{escape(b.client_name)}</a>'
    if b.username:
        contact += f" (@{escape(b.username)})"
    return (
        f"🔔 <b>Новая запись</b> · <code>{b.id}</code>\n\n"
        f"🏠 {escape(biz.title)}\n"
        f"📅 <b>{human_date(b.day)}, {hm(b.start)}</b>\n"
        f"👤 Мастер: {escape(b.master)}\n"
        f"🧾 {escape(b.service)} · {duration_text(b.duration)} · {biz.format_price(b.price)}\n\n"
        f"🙋 Клиент: {contact}\n"
        f"📱 {escape(pretty_phone(b.phone))}"
    )


def owner_cancel_alert(biz: Business, b: Booking) -> str:
    return (
        f"❌ <b>Клиент отменил запись</b> · <code>{b.id}</code>\n\n"
        f"🏠 {escape(biz.title)}\n"
        f"📅 {human_date(b.day)}, {hm(b.start)} · {escape(b.master)}\n"
        f"🧾 {escape(b.service)}\n"
        f"🙋 {escape(b.client_name)}, {escape(pretty_phone(b.phone))}\n\n"
        f"Окно снова доступно для записи."
    )


def client_cancelled_by_owner(biz: Business, b: Booking) -> str:
    contact = f"\nСвяжитесь с нами: {escape(biz.phone)}" if biz.phone else ""
    return (
        f"😔 К сожалению, ваша запись <code>{b.id}</code> в {escape(biz.title)} "
        f"на {human_date(b.day)}, {hm(b.start)} отменена администратором.{contact}\n\n"
        f"Вы можете выбрать другое время 👇"
    )


def my_bookings(biz: Business, bookings: list[Booking]) -> str:
    if not bookings:
        return "У вас пока нет предстоящих записей. Самое время записаться! 🙂"
    lines = [f"<b>Ваши записи в {escape(biz.title)}:</b>", ""]
    for b in bookings:
        lines.append(
            f"• <b>{human_date(b.day)}, {hm(b.start)}</b>\n"
            f"   {escape(b.service)} · {escape(b.master)} · <code>{b.id}</code>"
        )
    return "\n".join(lines)


def day_schedule(day: date, groups: list[tuple[Business, list[Booking]]]) -> str:
    lines = [f"📋 <b>Записи на {human_date(day)}</b>"]
    total = 0
    for biz, bookings in groups:
        if len(groups) > 1:
            lines += ["", f"<b>{escape(biz.title)}</b>"]
        if not bookings:
            lines.append("— записей нет")
        for b in bookings:
            total += 1
            phone = escape(pretty_phone(b.phone)) if b.phone else "—"
            lines.append(
                f"{hm(b.start)}–{hm(b.end_dt.time())} · <b>{escape(b.master)}</b>\n"
                f"   {escape(b.service)} · {escape(b.client_name or '—')} · {phone}"
            )
    lines += ["", f"Всего: {total}"]
    return "\n".join(lines)


ASK_NAME = "Почти готово! ✍️ Как к вам обращаться?\n\nНапишите имя или нажмите кнопку ниже."
ASK_PHONE = (
    "📱 Оставьте номер телефона — мастер свяжется, если что-то изменится.\n\n"
    "Нажмите «Отправить номер» или введите вручную, например <code>+7 999 123-45-67</code>."
)
BAD_NAME = "Имя должно быть от 2 до 40 символов, без ссылок и цифр. Попробуйте ещё раз:"
BAD_PHONE = "🤔 Не похоже на номер телефона. Введите в формате <code>+7 999 123-45-67</code> или <code>89991234567</code>:"
FOREIGN_CONTACT = "Пожалуйста, отправьте свой номер кнопкой ниже или введите его вручную."
CONFIRM = "Проверьте, всё ли верно:"
CANCELLED_FLOW = "Запись отменена. Возвращайтесь, когда будет удобно 👋"
SESSION_EXPIRED = "Сессия записи устарела — начните, пожалуйста, заново."
CANCEL_ASK = "Точно отменить эту запись?"
DEMO_NOTE = "👀 <b>Демо-режим:</b> вот так это уведомление пришло владельцу в личку:"
HELP = (
    "<b>Что умеет бот</b>\n\n"
    "📅 /book — записаться: мастер → услуга → день → время\n"
    "🗂 /my — ваши записи и отмена\n"
    "ℹ️ /about — адрес, мастера и цены\n"
    "🏠 /start — главное меню\n"
)
OWNER_HELP = (
    "\n<b>Для владельца</b>\n"
    "📋 /today — расписание на сегодня (листается по дням)\n"
    "🆔 /id — показать ваш Telegram ID\n\n"
    "Записи сразу попадают в Google Таблицу. Чтобы закрыть время вручную, добавьте в таблицу строку "
    "с датой, временем, длительностью и мастером (или словом «Все» — закрыть для всех)."
)
