"""Команды владельца: расписание на день и отмена записи из уведомления."""
from __future__ import annotations

from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts
from ..context import AppContext, show


def build_owner_router(owner_ids: frozenset[int]) -> Router:
    router = Router(name="owner")
    is_owner = F.from_user.id.in_(owner_ids)
    router.message.filter(is_owner)
    router.callback_query.filter(is_owner)

    async def _schedule(app: AppContext, day: date) -> str:
        groups = [(biz, await app.services[biz.id].bookings_on(day)) for biz in app.businesses.values()]
        return texts.day_schedule(day, groups)

    @router.message(Command("today"))
    async def cmd_today(message: Message, app: AppContext) -> None:
        today = next(iter(app.services.values())).now().date()
        await message.answer(await _schedule(app, today), reply_markup=kb.owner_days(today))

    @router.callback_query(kb.OwnerDayCb.filter())
    async def on_day(cb: CallbackQuery, callback_data: kb.OwnerDayCb, app: AppContext) -> None:
        day = datetime.strptime(callback_data.day, "%Y%m%d").date()
        await show(cb, await _schedule(app, day), kb.owner_days(day))
        await cb.answer()

    @router.callback_query(kb.OwnerCancelCb.filter())
    async def on_owner_cancel(cb: CallbackQuery, callback_data: kb.OwnerCancelCb, app: AppContext, bot: Bot) -> None:
        biz = app.businesses[callback_data.biz]
        booking = await app.services[biz.id].cancel(callback_data.id, by_owner=True)
        if booking is None:
            await cb.answer("Запись уже отменена или не найдена", show_alert=True)
            return
        if cb.message and cb.message.html_text:
            await show(cb, cb.message.html_text + "\n\n❌ <b>Отменена вами.</b> Клиент получил уведомление.")
        await cb.answer("Запись отменена, клиент уведомлён")
        try:
            await bot.send_message(
                booking.user_id, texts.client_cancelled_by_owner(biz, booking), reply_markup=kb.back_to_menu(biz)
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            await cb.message.answer("⚠️ Не удалось написать клиенту — позвоните ему по телефону из записи.")

    return router
