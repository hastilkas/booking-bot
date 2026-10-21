"""Точка входа: python -m bot"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent

from .booking_service import BookingService
from .catalog import load_businesses
from .config import ConfigError, load_settings
from .context import AppContext
from .handlers import build_router
from .storage import build_storages

log = logging.getLogger("bot")

USER_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="book", description="Записаться"),
    BotCommand(command="my", description="Мои записи"),
    BotCommand(command="about", description="Адрес, мастера и цены"),
    BotCommand(command="help", description="Помощь"),
]
OWNER_COMMANDS = USER_COMMANDS + [
    BotCommand(command="today", description="Расписание на сегодня"),
    BotCommand(command="id", description="Мой Telegram ID"),
]


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("%s", exc)
        sys.exit(1)

    businesses = load_businesses(settings.presets_dir, settings.presets)
    storages = build_storages(settings, businesses)
    services = {
        biz_id: BookingService(
            biz,
            storages[biz_id],
            settings.tz,
            days_ahead=settings.days_ahead,
            min_lead_minutes=settings.min_lead_minutes,
            max_active_per_user=settings.max_active_per_user,
        )
        for biz_id, biz in businesses.items()
    }
    app = AppContext(settings=settings, businesses=businesses, services=services)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage(), app=app)
    dp.include_router(build_router(settings.owner_ids))

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Ошибка при обработке апдейта", exc_info=event.exception)
        update = event.update
        try:
            if update.callback_query:
                await update.callback_query.answer("Что-то пошло не так, попробуйте ещё раз", show_alert=True)
            elif update.message:
                await update.message.answer("Что-то пошло не так 😔 Попробуйте ещё раз или нажмите /start")
        except Exception:  # noqa: BLE001 — не даём упасть обработчику ошибок
            pass
        return True

    await bot.set_my_commands(USER_COMMANDS)
    for owner_id in settings.owner_ids:
        try:
            await bot.set_my_commands(OWNER_COMMANDS, scope=BotCommandScopeChat(chat_id=owner_id))
        except Exception as exc:  # noqa: BLE001
            log.warning("Не удалось выставить команды владельцу %s: %s", owner_id, exc)

    me = await bot.get_me()
    log.info(
        "Бот @%s запущен: заведения=%s, хранилище=%s, демо=%s, владельцы=%s",
        me.username, ", ".join(businesses), settings.storage, settings.demo_mode, sorted(settings.owner_ids) or "не заданы",
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
