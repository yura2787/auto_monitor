import asyncio
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 0.5) -> None:
        self._rate = rate
        self._users: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        import time

        if isinstance(event, Update):
            user = None
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

            if user:
                now = time.monotonic()
                last = self._users.get(user.id, 0.0)
                if now - last < self._rate:
                    return None
                self._users[user.id] = now

        return await handler(event, data)
