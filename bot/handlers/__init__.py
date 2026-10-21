from aiogram import Router

from .owner import build_owner_router
from .user import router as user_router


def build_router(owner_ids: frozenset[int]) -> Router:
    root = Router(name="root")
    # роутер владельца первым: у клиентского в конце есть «ловушка» для любых сообщений
    root.include_router(build_owner_router(owner_ids))
    root.include_router(user_router)
    return root
