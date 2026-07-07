from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.keyboards import main_menu_kb
from models.filter import Filter
from models.listing import Listing
from models.user import User

router = Router()


@router.message(Command("stats"))
@router.callback_query(lambda c: c.data == "stats")
async def show_stats(event: Message | CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(Filter)
        .join(User)
        .where(User.telegram_id == event.from_user.id)
        .order_by(Filter.created_at.desc())
    )
    filters = list(result.scalars().all())

    if not filters:
        text = "📊 You have no filters yet."
    else:
        lines = ["📊 <b>Overall statistics</b>\n"]
        for fltr in filters:
            count = (await session.execute(
                select(func.count(Listing.id)).where(Listing.filter_id == fltr.id)
            )).scalar_one()

            min_price = (await session.execute(
                select(func.min(Listing.price)).where(
                    Listing.filter_id == fltr.id, Listing.price.isnot(None)
                )
            )).scalar_one()

            avg_price = (await session.execute(
                select(func.avg(Listing.price)).where(
                    Listing.filter_id == fltr.id, Listing.price.isnot(None)
                )
            )).scalar_one()

            status = "✅" if fltr.is_active else "⏸"
            lines.append(f"{status} <b>{fltr.display_name()}</b>")
            lines.append(f"— Total found: {count}")
            if min_price:
                lines.append(f"— Min price: ${int(min_price):,}".replace(",", " "))
            if avg_price:
                lines.append(f"— Avg price: ${int(avg_price):,}".replace(",", " "))
            lines.append("")

        text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
