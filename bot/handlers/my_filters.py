from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.keyboards import filters_list_kb, filter_actions_kb, confirm_delete_kb, main_menu_kb
from models.filter import Filter
from models.user import User

router = Router()


async def _get_user_filters(session: AsyncSession, telegram_id: int) -> list[Filter]:
    result = await session.execute(
        select(Filter)
        .join(User)
        .where(User.telegram_id == telegram_id)
        .order_by(Filter.created_at.desc())
    )
    return list(result.scalars().all())


@router.message(Command("list"))
@router.callback_query(lambda c: c.data == "my_filters")
async def show_filters(event: Message | CallbackQuery, session: AsyncSession) -> None:
    filters = await _get_user_filters(session, event.from_user.id)

    if filters:
        text = "📋 <b>My filters:</b>"
        kb = filters_list_kb(filters)
    else:
        text = "You have no filters yet.\nAdd your first one!"
        kb = main_menu_kb()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda c: c.data and c.data.startswith("filter:"))
async def show_filter_detail(call: CallbackQuery, session: AsyncSession) -> None:
    filter_id = int(call.data.split(":")[1])
    result = await session.execute(select(Filter).where(Filter.id == filter_id))
    fltr = result.scalar_one_or_none()

    if not fltr:
        await call.answer("Filter not found", show_alert=True)
        return

    status = "✅ Active" if fltr.is_active else "⏸ Paused"
    text = (
        f"🔍 <b>{fltr.display_name()}</b>\n\n"
        f"Status: {status}\n"
        f"📅 Year: {fltr.year_from or '—'} – {fltr.year_to or '—'}\n"
        f"💵 Price: ${fltr.price_from or 0} – ${fltr.price_to or '∞'}\n"
        f"🛣 Mileage: {fltr.mileage_from or 0} – {fltr.mileage_to or '∞'} k km\n"
        f"🏷 Condition: {fltr.condition or 'any'}"
    )
    await call.message.edit_text(
        text,
        reply_markup=filter_actions_kb(fltr.id, fltr.is_active),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pause:"))
async def pause_filter(call: CallbackQuery, session: AsyncSession) -> None:
    filter_id = int(call.data.split(":")[1])
    result = await session.execute(select(Filter).where(Filter.id == filter_id))
    fltr = result.scalar_one_or_none()
    if fltr:
        fltr.is_active = False
        await session.commit()
    await call.answer("⏸ Monitoring paused")
    await show_filter_detail(call, session)


@router.callback_query(lambda c: c.data and c.data.startswith("resume:"))
async def resume_filter(call: CallbackQuery, session: AsyncSession) -> None:
    filter_id = int(call.data.split(":")[1])
    result = await session.execute(select(Filter).where(Filter.id == filter_id))
    fltr = result.scalar_one_or_none()
    if fltr:
        fltr.is_active = True
        await session.commit()
    await call.answer("▶️ Monitoring resumed")
    await show_filter_detail(call, session)


@router.callback_query(lambda c: c.data and c.data.startswith("delete:"))
async def ask_delete(call: CallbackQuery, session: AsyncSession) -> None:
    filter_id = int(call.data.split(":")[1])
    result = await session.execute(select(Filter).where(Filter.id == filter_id))
    fltr = result.scalar_one_or_none()
    if not fltr:
        await call.answer("Filter not found", show_alert=True)
        return
    await call.message.edit_text(
        f"🗑 Delete filter <b>{fltr.display_name()}</b>?\n\n"
        "All found listings will also be removed.",
        reply_markup=confirm_delete_kb(filter_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete:"))
async def confirm_delete(call: CallbackQuery, session: AsyncSession) -> None:
    filter_id = int(call.data.split(":")[1])
    result = await session.execute(select(Filter).where(Filter.id == filter_id))
    fltr = result.scalar_one_or_none()
    if fltr:
        await session.delete(fltr)
        await session.commit()
    await call.message.edit_text("✅ Filter deleted.", reply_markup=main_menu_kb())
    await call.answer()
