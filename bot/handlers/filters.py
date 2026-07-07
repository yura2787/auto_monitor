from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.states import AddFilterFSM
from bot.keyboards import confirm_filter_kb, condition_kb, skip_kb, cancel_kb
from bot.utils import safe_edit
from models.filter import Filter
from models.user import User

router = Router()


def _condition_label(val: str | None) -> str:
    return {"new": "New", "used": "Used", "damaged": "Damaged"}.get(val or "", "Any")


def _filter_summary(data: dict) -> str:
    lines = [
        f"🚗 <b>Brand:</b> {data.get('brand', '—')}",
        f"🔍 <b>Model:</b> {data.get('model') or 'any'}",
        f"📅 <b>Year:</b> {data.get('year_from') or '—'} – {data.get('year_to') or '—'}",
        f"💵 <b>Price:</b> ${data.get('price_from') or '0'} – ${data.get('price_to') or '∞'}",
        f"🛣 <b>Mileage:</b> {data.get('mileage_from') or '0'} – {data.get('mileage_to') or '∞'} k km",
        f"🏷 <b>Condition:</b> {_condition_label(data.get('condition'))}",
    ]
    return "\n".join(lines)


# ── wizard start ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data in ("add_filter", "restart_filter"))
async def start_wizard(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddFilterFSM.brand)
    await safe_edit(call.message, "🚗 Enter the car brand:\nExample: Toyota, BMW, Mercedes\n\nOr тойота, бмв, мерседес", reply_markup=cancel_kb())
    await call.answer()


# ── brand ─────────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.brand)
async def step_brand(message: Message, state: FSMContext) -> None:
    await state.update_data(brand=message.text.strip())
    await state.set_state(AddFilterFSM.model)
    await message.answer(
        "🔍 Enter the model:\nExample: Camry, X5, E-Class\n\nOr skip:",
        reply_markup=skip_kb(),
    )


# ── model ─────────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.model)
async def step_model(message: Message, state: FSMContext) -> None:
    await state.update_data(model=message.text.strip())
    await state.set_state(AddFilterFSM.year_from)
    await message.answer("📅 Year from:\nExample: 2015\n\nOr skip:", reply_markup=skip_kb())


# ── year from ─────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.year_from)
async def step_year_from(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 2015")
        return
    await state.update_data(year_from=int(val))
    await state.set_state(AddFilterFSM.year_to)
    await message.answer("📅 Year to:\nExample: 2022\n\nOr skip:", reply_markup=skip_kb())


# ── year to ───────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.year_to)
async def step_year_to(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 2022")
        return
    await state.update_data(year_to=int(val))
    await state.set_state(AddFilterFSM.price_from)
    await message.answer("💵 Price from (USD):\nExample: 5000\n\nOr skip:", reply_markup=skip_kb())


# ── price from ────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.price_from)
async def step_price_from(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 5000")
        return
    await state.update_data(price_from=int(val))
    await state.set_state(AddFilterFSM.price_to)
    await message.answer("💵 Price to (USD):\nExample: 20000\n\nOr skip:", reply_markup=skip_kb())


# ── price to ──────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.price_to)
async def step_price_to(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 20000")
        return
    await state.update_data(price_to=int(val))
    await state.set_state(AddFilterFSM.mileage_from)
    await message.answer("🛣 Mileage from (k km):\nExample: 0\n\nOr skip:", reply_markup=skip_kb())


# ── mileage from ──────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.mileage_from)
async def step_mileage_from(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 0")
        return
    await state.update_data(mileage_from=int(val))
    await state.set_state(AddFilterFSM.mileage_to)
    await message.answer("🛣 Mileage to (k km):\nExample: 150\n\nOr skip:", reply_markup=skip_kb())


# ── mileage to ────────────────────────────────────────────────────────────────

@router.message(AddFilterFSM.mileage_to)
async def step_mileage_to(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Please enter a number, e.g. 150")
        return
    await state.update_data(mileage_to=int(val))
    await state.set_state(AddFilterFSM.condition)
    await message.answer("🏷 Car condition:", reply_markup=condition_kb())


# ── condition (callback) ──────────────────────────────────────────────────────

@router.callback_query(AddFilterFSM.condition, lambda c: c.data.startswith("condition:"))
async def step_condition(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":")[1]
    await state.update_data(condition=None if value == "any" else value)
    await state.set_state(AddFilterFSM.confirm)

    data = await state.get_data()
    await safe_edit(
        call.message,
        f"📋 <b>Review your filter:</b>\n\n{_filter_summary(data)}",
        reply_markup=confirm_filter_kb(),
    )
    await call.answer()


# ── skip ──────────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "skip")
async def cb_skip(call: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()

    # maps current state → (next state, prompt text, has skip button)
    state_map = {
        AddFilterFSM.model.state:        (AddFilterFSM.year_from,    "📅 Year from:\nOr skip:",           True),
        AddFilterFSM.year_from.state:    (AddFilterFSM.year_to,      "📅 Year to:\nOr skip:",             True),
        AddFilterFSM.year_to.state:      (AddFilterFSM.price_from,   "💵 Price from (USD):\nOr skip:",    True),
        AddFilterFSM.price_from.state:   (AddFilterFSM.price_to,     "💵 Price to (USD):\nOr skip:",      True),
        AddFilterFSM.price_to.state:     (AddFilterFSM.mileage_from, "🛣 Mileage from (k km):\nOr skip:", True),
        AddFilterFSM.mileage_from.state: (AddFilterFSM.mileage_to,   "🛣 Mileage to (k km):\nOr skip:",  True),
        AddFilterFSM.mileage_to.state:   (AddFilterFSM.condition,    "🏷 Car condition:",                 False),
    }

    if current not in state_map:
        await call.answer()
        return

    next_state, text, has_skip = state_map[current]
    await state.set_state(next_state)

    if next_state == AddFilterFSM.condition:
        await safe_edit(call.message, text, reply_markup=condition_kb())
    else:
        await safe_edit(call.message, text, reply_markup=skip_kb() if has_skip else None)
    await call.answer()


# ── confirm ───────────────────────────────────────────────────────────────────

@router.callback_query(AddFilterFSM.confirm, lambda c: c.data == "confirm_filter")
async def cb_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()

    result = await session.execute(
        select(User).where(User.telegram_id == call.from_user.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        await call.answer("Please send /start first", show_alert=True)
        return

    fltr = Filter(
        user_id=user.id,
        brand=data["brand"],
        model=data.get("model"),
        year_from=data.get("year_from"),
        year_to=data.get("year_to"),
        price_from=data.get("price_from"),
        price_to=data.get("price_to"),
        mileage_from=data.get("mileage_from"),
        mileage_to=data.get("mileage_to"),
        condition=data.get("condition"),
    )
    session.add(fltr)
    await session.commit()

    from bot.keyboards import main_menu_kb
    await safe_edit(
        call.message,
        f"✅ Filter <b>{fltr.display_name()}</b> saved!\n\n"
        "I will notify you as soon as I find new listings. 🔍",
        reply_markup=main_menu_kb(),
    )
    await call.answer()


# ── cancel ────────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "cancel_filter")
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    from bot.keyboards import main_menu_kb
    await safe_edit(call.message, "Cancelled. Back to menu.", reply_markup=main_menu_kb())
    await call.answer()
