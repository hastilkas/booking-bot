"""Сценарий клиента: меню → мастер → услуга → день → время → имя → телефон → подтверждение."""
from __future__ import annotations

import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import keyboards as kb
from .. import texts
from ..booking_service import BookingError, SlotTakenError
from ..catalog import Business
from ..context import AppContext, show
from ..phone import normalize_phone

router = Router(name="user")

NAME_RE = re.compile(r"^[^\d@/<>\\#*_]{2,40}$")


class Form(StatesGroup):
    name = State()
    phone = State()
    confirm = State()


def _parse_day(value: str):
    return datetime.strptime(value, "%Y%m%d").date()


def _parse_time(value: str):
    return datetime.strptime(value, "%H%M").time()


# --- меню ------------------------------------------------------------------
async def _send_menu(message: Message, app: AppContext, biz: Business, first_name: str) -> None:
    await message.answer(texts.welcome(biz, first_name), reply_markup=kb.main_menu(biz, app.multi))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, app: AppContext) -> None:
    await state.clear()
    if app.multi and message.from_user.id not in app.user_biz:
        await message.answer(
            "Привет! 👋 Это демо бота онлайн-записи.\n\nВыберите заведение — бот подстроится под нишу:",
            reply_markup=kb.business_picker(app.businesses),
        )
        return
    await _send_menu(message, app, app.biz_for(message.from_user.id), message.from_user.first_name)


@router.message(Command("help"))
async def cmd_help(message: Message, app: AppContext) -> None:
    text = texts.HELP + (texts.OWNER_HELP if app.is_owner(message.from_user.id) else "")
    await message.answer(text)


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>\nУкажите его в OWNER_IDS, чтобы получать уведомления.")


@router.message(Command("about"))
async def cmd_about(message: Message, app: AppContext) -> None:
    biz = app.biz_for(message.from_user.id)
    await message.answer(texts.about(biz), reply_markup=kb.back_to_menu(biz))


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext, app: AppContext) -> None:
    await state.clear()
    biz = app.biz_for(message.from_user.id)
    await message.answer(texts.choose_master(biz), reply_markup=kb.masters(biz))


@router.message(Command("my"))
async def cmd_my(message: Message, app: AppContext) -> None:
    biz = app.biz_for(message.from_user.id)
    bookings = await app.services[biz.id].user_bookings(message.from_user.id)
    await message.answer(texts.my_bookings(biz, bookings), reply_markup=kb.my_bookings(biz, bookings))


@router.callback_query(kb.BizCb.filter())
async def on_business(cb: CallbackQuery, callback_data: kb.BizCb, state: FSMContext, app: AppContext) -> None:
    await state.clear()
    biz = app.businesses[callback_data.biz]
    app.remember(cb.from_user.id, biz.id)
    await show(cb, texts.welcome(biz, cb.from_user.first_name), kb.main_menu(biz, app.multi))
    await cb.answer()


@router.callback_query(kb.MenuCb.filter())
async def on_menu(cb: CallbackQuery, callback_data: kb.MenuCb, state: FSMContext, app: AppContext) -> None:
    await state.clear()
    biz = app.businesses[callback_data.biz]
    app.remember(cb.from_user.id, biz.id)
    action = callback_data.action
    if action == "book":
        await show(cb, texts.choose_master(biz), kb.masters(biz))
    elif action == "my":
        bookings = await app.services[biz.id].user_bookings(cb.from_user.id)
        await show(cb, texts.my_bookings(biz, bookings), kb.my_bookings(biz, bookings))
    elif action == "about":
        await show(cb, texts.about(biz), kb.back_to_menu(biz))
    elif action == "switch":
        await show(cb, "Выберите заведение:", kb.business_picker(app.businesses))
    else:
        await show(cb, texts.welcome(biz, cb.from_user.first_name), kb.main_menu(biz, app.multi))
    await cb.answer()


# --- выбор мастера / услуги / дня / времени ----------------------------------
@router.callback_query(kb.MasterCb.filter())
async def on_master(cb: CallbackQuery, callback_data: kb.MasterCb, app: AppContext) -> None:
    biz = app.businesses[callback_data.biz]
    master = biz.masters[callback_data.master]
    await show(cb, texts.choose_service(master), kb.services(biz, master.id))
    await cb.answer()


@router.callback_query(kb.ServiceCb.filter())
async def on_service(cb: CallbackQuery, callback_data: kb.ServiceCb, app: AppContext) -> None:
    biz = app.businesses[callback_data.biz]
    master = biz.masters[callback_data.master]
    service = biz.services[callback_data.service]
    overview = await app.services[biz.id].days_overview(master.id, service.id)
    await show(
        cb,
        texts.choose_day(master, service, has_days=any(overview.values())),
        kb.days(biz, master.id, service.id, overview),
    )
    await cb.answer()


@router.callback_query(kb.DayCb.filter())
async def on_day(cb: CallbackQuery, callback_data: kb.DayCb, app: AppContext) -> None:
    biz = app.businesses[callback_data.biz]
    master = biz.masters[callback_data.master]
    service = biz.services[callback_data.service]
    day = _parse_day(callback_data.day)
    slots = await app.services[biz.id].free_slots(master.id, service.id, day)
    if not slots:
        await cb.answer("В этот день окна уже закончились 😔", show_alert=True)
        overview = await app.services[biz.id].days_overview(master.id, service.id)
        await show(cb, texts.choose_day(master, service, any(overview.values())), kb.days(biz, master.id, service.id, overview))
        return
    await show(cb, texts.choose_time(master, service, day), kb.times(biz, master.id, service.id, day, slots))
    await cb.answer()


@router.callback_query(F.data == kb.NOOP)
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer("В этот день нет свободных окон")


@router.callback_query(kb.TimeCb.filter())
async def on_time(cb: CallbackQuery, callback_data: kb.TimeCb, state: FSMContext, app: AppContext) -> None:
    biz = app.businesses[callback_data.biz]
    master = biz.masters[callback_data.master]
    service = biz.services[callback_data.service]
    day, start = _parse_day(callback_data.day), _parse_time(callback_data.time)

    slots = await app.services[biz.id].free_slots(master.id, service.id, day)
    if start not in slots:
        await cb.answer("Это время только что заняли, выберите другое", show_alert=True)
        await show(cb, texts.choose_time(master, service, day), kb.times(biz, master.id, service.id, day, slots))
        return

    await state.set_state(Form.name)
    await state.set_data(
        {"biz": biz.id, "master": master.id, "service": service.id, "day": callback_data.day, "time": callback_data.time}
    )
    await show(cb, "Вы выбрали:\n\n" + texts.booking_card(biz, master.name, service, service.price, day, start))
    await cb.message.answer(texts.ASK_NAME, reply_markup=kb.ask_name(cb.from_user.first_name))
    await cb.answer()


# --- имя и телефон -----------------------------------------------------------
@router.message(StateFilter(Form.name, Form.phone, Form.confirm), F.text == kb.BTN_CANCEL)
async def on_flow_cancel(message: Message, state: FSMContext, app: AppContext) -> None:
    await state.clear()
    biz = app.biz_for(message.from_user.id)
    await message.answer(texts.CANCELLED_FLOW, reply_markup=ReplyKeyboardRemove())
    await _send_menu(message, app, biz, message.from_user.first_name)


@router.message(Form.name, F.text)
async def on_name(message: Message, state: FSMContext) -> None:
    name = " ".join(message.text.split())
    if not NAME_RE.match(name) or "http" in name.lower():
        await message.answer(texts.BAD_NAME)
        return
    await state.update_data(name=name)
    await state.set_state(Form.phone)
    await message.answer(texts.ASK_PHONE, reply_markup=kb.ask_phone())


@router.message(Form.name)
async def on_name_other(message: Message) -> None:
    await message.answer(texts.BAD_NAME)


async def _accept_phone(message: Message, state: FSMContext, app: AppContext, raw: str) -> None:
    phone = normalize_phone(raw, app.settings.phone_region)
    if phone is None:
        await message.answer(texts.BAD_PHONE, reply_markup=kb.ask_phone())
        return
    data = await state.update_data(phone=phone)
    await state.set_state(Form.confirm)

    biz = app.businesses[data["biz"]]
    service = biz.services[data["service"]]
    card = texts.booking_card(
        biz, biz.masters[data["master"]].name, service, service.price,
        _parse_day(data["day"]), _parse_time(data["time"]), data["name"], phone,
    )
    await message.answer("👍 Номер принят", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"{texts.CONFIRM}\n\n{card}", reply_markup=kb.confirm())


@router.message(Form.phone, F.contact)
async def on_contact(message: Message, state: FSMContext, app: AppContext) -> None:
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(texts.FOREIGN_CONTACT, reply_markup=kb.ask_phone())
        return
    raw = contact.phone_number
    await _accept_phone(message, state, app, raw if raw.startswith("+") else f"+{raw}")


@router.message(Form.phone, F.text)
async def on_phone_text(message: Message, state: FSMContext, app: AppContext) -> None:
    await _accept_phone(message, state, app, message.text)


@router.message(Form.phone)
async def on_phone_other(message: Message) -> None:
    await message.answer(texts.BAD_PHONE, reply_markup=kb.ask_phone())


# --- подтверждение ------------------------------------------------------------
@router.callback_query(Form.confirm, kb.ConfirmCb.filter(F.action == "yes"))
async def on_confirm(cb: CallbackQuery, state: FSMContext, app: AppContext, bot: Bot) -> None:
    data = await state.get_data()
    biz = app.businesses[data["biz"]]
    service_api = app.services[biz.id]
    day, start = _parse_day(data["day"]), _parse_time(data["time"])
    try:
        booking = await service_api.book(
            master_id=data["master"],
            service_id=data["service"],
            day=day,
            start=start,
            client_name=data["name"],
            phone=data["phone"],
            user_id=cb.from_user.id,
            username=cb.from_user.username or "",
        )
    except SlotTakenError as exc:
        await state.clear()
        master, service = biz.masters[data["master"]], biz.services[data["service"]]
        slots = await service_api.free_slots(master.id, service.id, day)
        await cb.answer()
        await show(cb, f"{exc}\n\n{texts.choose_time(master, service, day)}",
                   kb.times(biz, master.id, service.id, day, slots))
        return
    except BookingError as exc:
        await state.clear()
        bookings = await service_api.user_bookings(cb.from_user.id)
        await cb.answer()
        await show(cb, str(exc), kb.my_bookings(biz, bookings))
        return

    await state.clear()
    await cb.answer("Готово! 🎉")
    await show(cb, texts.booking_confirmed(biz, booking), kb.after_booking(biz))

    alert = texts.owner_alert(biz, booking)
    await app.notify_owners(bot, alert, kb.owner_alert(biz, booking.id))
    if app.settings.demo_mode and not app.is_owner(cb.from_user.id):
        await cb.message.answer(f"{texts.DEMO_NOTE}\n\n{alert}")


@router.callback_query(Form.confirm, kb.ConfirmCb.filter(F.action == "no"))
async def on_confirm_no(cb: CallbackQuery, state: FSMContext, app: AppContext) -> None:
    data = await state.get_data()
    await state.clear()
    biz = app.businesses.get(data.get("biz")) or app.biz_for(cb.from_user.id)
    await show(cb, texts.CANCELLED_FLOW, kb.back_to_menu(biz))
    await cb.answer()


@router.callback_query(kb.ConfirmCb.filter())
async def on_confirm_stale(cb: CallbackQuery, app: AppContext) -> None:
    # кнопка из старого сообщения или бот перезапускался между шагами
    biz = app.biz_for(cb.from_user.id)
    await show(cb, texts.SESSION_EXPIRED, kb.back_to_menu(biz))
    await cb.answer()


# --- мои записи и отмена ---------------------------------------------------------
@router.callback_query(kb.CancelCb.filter())
async def on_cancel(cb: CallbackQuery, callback_data: kb.CancelCb, app: AppContext, bot: Bot) -> None:
    biz = app.businesses[callback_data.biz]
    service_api = app.services[biz.id]

    if callback_data.step == "ask":
        booking = await service_api.get(callback_data.id)
        if booking is None or not booking.is_active or booking.user_id != cb.from_user.id:
            await cb.answer("Запись не найдена или уже отменена", show_alert=True)
            return
        card = texts.booking_card(biz, booking.master, booking.service, booking.price, booking.day, booking.start)
        await show(cb, f"{texts.CANCEL_ASK}\n\n{card}", kb.cancel_confirm(biz, booking.id))
        await cb.answer()
        return

    if callback_data.step == "yes":
        booking = await service_api.cancel(callback_data.id, by_owner=False, user_id=cb.from_user.id)
        if booking is None:
            await cb.answer("Запись не найдена или уже отменена", show_alert=True)
        else:
            await cb.answer("Запись отменена")
            await app.notify_owners(bot, texts.owner_cancel_alert(biz, booking))

    bookings = await service_api.user_bookings(cb.from_user.id)
    await show(cb, texts.my_bookings(biz, bookings), kb.my_bookings(biz, bookings))
    if callback_data.step == "no":
        await cb.answer()


@router.message(StateFilter(None))
async def fallback(message: Message, app: AppContext) -> None:
    biz = app.biz_for(message.from_user.id)
    await message.answer("Я бот для онлайн-записи 🙂 Выберите действие:", reply_markup=kb.main_menu(biz, app.multi))
