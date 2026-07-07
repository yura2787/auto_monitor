from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.keyboards import main_menu_kb
from models.user import User

router = Router()


async def _get_or_create_user(session: AsyncSession, message: Message) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        session.add(user)
        await session.commit()
    return user


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await _get_or_create_user(session, message)
    name = message.from_user.first_name or "there"
    await message.answer(
        f"👋 Hey, {name}!\n\n"
        "I monitor OLX listings and notify you about new cars "
        "right after they are published.\n\n"
        "Choose an action:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(lambda c: c.data == "main_menu")
async def cb_main_menu(call: CallbackQuery) -> None:
    await call.message.edit_text("Choose an action:", reply_markup=main_menu_kb())
    await call.answer()
