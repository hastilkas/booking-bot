"""Сквозной тест: прогоняем реальный диалог через диспетчер aiogram, подменив только сеть."""
from __future__ import annotations

import itertools
from datetime import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update, User

from bot.context import AppContext
from bot.handlers import build_router

from conftest import ROOT, TZ

CLIENT = User(id=111, is_bot=False, first_name="Иван", username="ivan")
OWNER_ID = 999
_ids = itertools.count(1)
# Роутеры aiogram можно подключить только один раз, поэтому диспетчер общий на модуль,
# а свежий AppContext передаём в каждый апдейт.
DP = Dispatcher(storage=MemoryStorage())
DP.include_router(build_router(frozenset({OWNER_ID})))


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            chat_id = getattr(method, "chat_id", None) or CLIENT.id
            return Message(message_id=next(_ids), date=datetime.now(), chat=Chat(id=chat_id, type="private"),
                           text=method.text)
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self):
        pass


class Harness:
    def __init__(self, app: AppContext) -> None:
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session)
        self.app = app

    def _msg(self, **kw) -> Message:
        return Message(message_id=next(_ids), date=datetime.now(), chat=Chat(id=CLIENT.id, type="private"),
                       from_user=CLIENT, **kw)

    async def send(self, **kw):
        self.session.calls.clear()
        await DP.feed_update(self.bot, Update(update_id=next(_ids), message=self._msg(**kw)), app=self.app)
        return self.session.calls

    async def press(self, callback_data: str):
        self.session.calls.clear()
        cb = CallbackQuery(id=str(next(_ids)), from_user=CLIENT, chat_instance="x", data=callback_data,
                           message=self._msg(text="old"))
        await DP.feed_update(self.bot, Update(update_id=next(_ids), callback_query=cb), app=self.app)
        return self.session.calls

    @staticmethod
    def buttons(calls) -> dict[str, str]:
        """Все inline-кнопки из ответов бота: текст -> callback_data."""
        out = {}
        for c in calls:
            markup = getattr(c, "reply_markup", None)
            for row in getattr(markup, "inline_keyboard", None) or []:
                for b in row:
                    out[b.text] = b.callback_data
        return out

    @staticmethod
    def texts(calls) -> str:
        return "\n".join(c.text for c in calls if isinstance(c, (SendMessage, EditMessageText)))


@pytest.fixture
def harness(service, barbershop):
    from bot.config import Settings

    settings = Settings(
        bot_token="42:TEST", owner_ids=frozenset({OWNER_ID}), presets=("barbershop",), presets_dir=ROOT / "presets",
        tz=TZ, storage="local", data_dir=ROOT / "data", google_credentials_file=ROOT / "x.json", spreadsheet_id="",
        days_ahead=14, min_lead_minutes=60, max_active_per_user=3, phone_region="RU", demo_mode=True,
    )
    app = AppContext(settings=settings, businesses={"barbershop": barbershop}, services={"barbershop": service})
    return Harness(app)


async def test_full_booking_flow(harness: Harness, service):
    h = harness
    calls = await h.send(text="/start")
    assert "Old Fox Barbershop" in h.texts(calls)

    calls = await h.press(h.buttons(calls)["📅 Записаться"])
    calls = await h.press(h.buttons(calls)["Алексей"])
    services = h.buttons(calls)
    calls = await h.press(next(v for k, v in services.items() if k.startswith("Мужская стрижка")))
    days = h.buttons(calls)
    assert "· Вс 25 окт ·" in days  # выходной показан, но некликабелен
    calls = await h.press(days["Завтра"])  # «сегодня» в тестах — пн 19 окт
    calls = await h.press(h.buttons(calls)["10:00"])
    assert "Как к вам обращаться" in h.texts(calls)

    calls = await h.send(text="1")
    assert "Имя должно быть" in h.texts(calls)
    calls = await h.send(text="Иван")
    assert "номер телефона" in h.texts(calls)

    calls = await h.send(text="позвоните мне")
    assert "Не похоже на номер" in h.texts(calls)
    calls = await h.send(contact=Contact(phone_number="79991234567", first_name="Иван", user_id=CLIENT.id))
    assert "Проверьте, всё ли верно" in h.texts(calls)

    calls = await h.press(h.buttons(calls)["✅ Подтвердить запись"])
    text = h.texts(calls)
    assert "Вы записаны" in text and "20 октября" in text and "10:00" in text

    owner_msgs = [c for c in calls if isinstance(c, SendMessage) and c.chat_id == OWNER_ID]
    assert len(owner_msgs) == 1 and "Новая запись" in owner_msgs[0].text and "+7 999 123-45-67" in owner_msgs[0].text
    assert "Демо-режим" in text  # клиент видит копию уведомления владельца

    [booking] = await service.user_bookings(CLIENT.id)
    assert booking.phone == "+79991234567" and booking.client_name == "Иван"

    # Отмена клиентом → владелец получает алерт, окно освобождается
    calls = await h.press(h.buttons(calls)["🗂 Мои записи"])
    cancel_btn = next(v for k, v in h.buttons(calls).items() if k.startswith("❌ Отменить"))
    calls = await h.press(cancel_btn)
    calls = await h.press(h.buttons(calls)["Да, отменить"])
    assert any(isinstance(c, SendMessage) and c.chat_id == OWNER_ID and "отменил" in c.text for c in calls)
    assert await service.user_bookings(CLIENT.id) == []


async def test_owner_commands_hidden_from_clients(harness: Harness):
    calls = await harness.send(text="/today")
    assert "Записи на" not in harness.texts(calls)


async def test_stale_confirm_button(harness: Harness):
    calls = await harness.press("ok:yes")
    assert "устарела" in harness.texts(calls)
    assert any(isinstance(c, AnswerCallbackQuery) for c in calls)
