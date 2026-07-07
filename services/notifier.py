from aiogram import Bot
from aiogram.types import InputMediaPhoto, URLInputFile

from parser.olx import OLXListing
from services.price_analyzer import PriceAnalysis
from models.filter import Filter


def _format_price(price: int) -> str:
    return f"${price:,}".replace(",", " ")  # non-breaking thin space


def _build_text(
    listing: OLXListing,
    fltr: Filter,
    analysis: Optional["PriceAnalysis"] = None,
) -> str:
    from typing import Optional  # local import щоб уникнути циклу

    lines: list[str] = [f"🚗 <b>{listing.title}</b>\n"]

    price_str = _format_price(listing.price) if listing.price else "Ціна не вказана"
    lines.append(f"💰 <b>Ціна:</b> {price_str}")

    if analysis:
        lines.append(f"{analysis.emoji} {analysis.verdict}")
        lines.append(
            f"📊 Середня по ринку: {_format_price(analysis.median_price)} "
            f"(на основі {analysis.sample_size} оголошень)"
        )

    lines.append("")

    if listing.year:
        lines.append(f"📅 <b>Рік:</b> {listing.year}")
    if listing.mileage:
        lines.append(f"🛣 <b>Пробіг:</b> {listing.mileage:,} км".replace(",", " "))
    if listing.engine:
        lines.append(f"⚙️ <b>Двигун:</b> {listing.engine}")
    if listing.city:
        lines.append(f"📍 {listing.city}")
    if listing.published_at:
        lines.append(f"🕐 <b>Опубліковано:</b> {listing.published_at}")

    lines.append(f"\n🔗 <a href='{listing.url}'>Переглянути на OLX</a>")
    return "\n".join(lines)


class Notifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_listing(
        self,
        chat_id: int,
        listing: OLXListing,
        fltr: Filter,
        analysis: "PriceAnalysis | None" = None,
    ) -> None:
        text = _build_text(listing, fltr, analysis)
        photos = listing.photos or []

        if len(photos) >= 2:
            media = [
                InputMediaPhoto(
                    media=URLInputFile(photos[0]),
                    caption=text,
                    parse_mode="HTML",
                ),
                *[InputMediaPhoto(media=URLInputFile(p)) for p in photos[1:4]],
            ]
            await self._bot.send_media_group(chat_id=chat_id, media=media)
        elif len(photos) == 1:
            await self._bot.send_photo(
                chat_id=chat_id,
                photo=URLInputFile(photos[0]),
                caption=text,
                parse_mode="HTML",
            )
        else:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

    async def send_daily_stats(self, chat_id: int, stats: list[dict]) -> None:
        if not stats:
            await self._bot.send_message(
                chat_id=chat_id,
                text="📊 Сьогодні нових оголошень не знайдено.",
            )
            return

        lines = ["📊 <b>Ваша статистика за сьогодні</b>\n"]
        for s in stats:
            lines.append(f"🔍 <b>{s['filter_name']}</b>:")
            lines.append(f"— Знайдено нових: {s['count']}")
            if s.get("min_price"):
                lines.append(f"— Мінімальна ціна: {_format_price(s['min_price'])}")
            if s.get("avg_price"):
                lines.append(f"— Середня ціна: {_format_price(s['avg_price'])}")
            if s.get("best_url"):
                lines.append(f"— Найкраща пропозиція: <a href='{s['best_url']}'>посилання</a>")
            lines.append("")

        await self._bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
