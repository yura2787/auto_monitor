import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers import start_router, filters_router, my_filters_router, stats_router
from bot.middlewares import ThrottlingMiddleware
from config.settings import settings
from models.base import engine, Base, AsyncSessionLocal


async def on_startup(bot: Bot) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database tables created")


# injects an async DB session into every handler via data["session"]
async def db_middleware(
    handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: dict[str, Any],
) -> Any:
    async with AsyncSessionLocal() as session:
        data["session"] = session
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(ThrottlingMiddleware(rate=0.5))
    dp.update.middleware(db_middleware)

    dp.include_router(start_router)
    dp.include_router(filters_router)
    dp.include_router(my_filters_router)
    dp.include_router(stats_router)

    await on_startup(bot)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
