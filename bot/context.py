from __future__ import annotations

import logging
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from .booking_service import BookingService
from .catalog import Business
from .config import Settings

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Всё, что нужно обработчикам. Передаётся в них через workflow_data диспетчера."""

    settings: Settings
    businesses: dict[str, Business]
    services: dict[str, BookingService]
    # какое заведение пользователь смотрел последним (для команд /book, /my, /about)
    user_biz: dict[int, str] = field(default_factory=dict)

    @property
    def multi(self) -> bool:
        return len(self.businesses) > 1

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.settings.owner_ids

    def biz_for(self, user_id: int) -> Business:
        biz_id = self.user_biz.get(user_id)
        return self.businesses.get(biz_id) or next(iter(self.businesses.values()))

    def remember(self, user_id: int, biz_id: str) -> None:
        self.user_biz[user_id] = biz_id

    async def notify_owners(self, bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
        for owner_id in self.settings.owner_ids:
            try:
                await bot.send_message(owner_id, text, reply_markup=markup)
            except (TelegramForbiddenError, TelegramBadRequest) as exc:
                # владелец ещё не нажал /start у бота или заблокировал его
                log.warning("Не удалось уведомить владельца %s: %s", owner_id, exc)


async def show(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение с кнопками; если это невозможно — присылает новое."""
    message = cb.message
    try:
        if isinstance(message, Message):
            await message.edit_text(text, reply_markup=markup)
            return
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        log.debug("edit_text failed, sending new message: %s", exc)
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=markup)
