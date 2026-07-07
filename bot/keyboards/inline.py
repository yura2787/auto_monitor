from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Add filter", callback_data="add_filter")
    builder.button(text="📋 My filters", callback_data="my_filters")
    builder.button(text="📊 Statistics", callback_data="stats")
    builder.adjust(1)
    return builder.as_markup()


def filters_list_kb(filters: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for fltr in filters:
        status = "✅" if fltr.is_active else "⏸"
        builder.button(
            text=f"{status} {fltr.display_name()}",
            callback_data=f"filter:{fltr.id}",
        )
    builder.button(text="◀️ Back to menu", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def filter_actions_kb(filter_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.button(text="⏸ Pause", callback_data=f"pause:{filter_id}")
    else:
        builder.button(text="▶️ Resume", callback_data=f"resume:{filter_id}")
    builder.button(text="🗑 Delete", callback_data=f"delete:{filter_id}")
    builder.button(text="◀️ Back to filters", callback_data="my_filters")
    builder.adjust(1)
    return builder.as_markup()


def confirm_filter_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm", callback_data="confirm_filter")
    builder.button(text="✏️ Start over", callback_data="restart_filter")
    builder.button(text="❌ Cancel", callback_data="cancel_filter")
    builder.adjust(2, 1)
    return builder.as_markup()


def condition_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="All", callback_data="condition:any")
    builder.button(text="New", callback_data="condition:new")
    builder.button(text="Used", callback_data="condition:used")
    builder.button(text="Damaged", callback_data="condition:damaged")
    builder.button(text="◀️ Cancel", callback_data="cancel_filter")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip ⏭", callback_data="skip")
    builder.button(text="◀️ Cancel", callback_data="cancel_filter")
    builder.adjust(2)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Cancel", callback_data="cancel_filter")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb(filter_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, delete", callback_data=f"confirm_delete:{filter_id}")
    builder.button(text="◀️ No, go back", callback_data=f"filter:{filter_id}")
    builder.adjust(2)
    return builder.as_markup()


def stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Back to menu", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
