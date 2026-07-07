import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InputMediaPhoto, URLInputFile

from parser.olx import OLXListing
from services.price_analyzer import PriceAnalysis
from models.filter import Filter


def _fmt_price(price: int) -> str:
    return f"${price:,}".replace(",", " ")


def _build_text(
    listing: OLXListing,
    fltr: Filter,
    analysis: Optional[PriceAnalysis] = None,
) -> str:
    lines: list[str] = [f"🚗 <b>{listing.title}</b>\n"]

    price_str = _fmt_price(listing.price) if listing.price else "Price not specified"
    lines.append(f"💰 <b>Price:</b> {price_str}")

    if analysis:
        lines.append(f"{analysis.emoji} {analysis.verdict}")
        lines.append(
            f"📊 Market median: {_fmt_price(analysis.median_price)} "
            f"(based on {analysis.sample_size} listings)"
        )

    lines.append("")

    if listing.year:
        lines.append(f"📅 <b>Year:</b> {listing.year}")
    if listing.mileage:
        lines.append(f"🛣 <b>Mileage:</b> {listing.mileage * 1000:,} km".replace(",", " "))
    if listing.engine:
        lines.append(f"⚙️ <b>Engine:</b> {listing.engine}")
    if listing.city:
        lines.append(f"📍 {listing.city}")
    if listing.published_at:
        lines.append(f"🕐 <b>Posted:</b> {listing.published_at}")

    lines.append(f"\n🔗 <a href='{listing.url}'>View on OLX</a>")
    return "\n".join(lines)


class Notifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_listing(
        self,
        chat_id: int,
        listing: OLXListing,
        fltr: Filter,
        analysis: Optional[PriceAnalysis] = None,
    ) -> None:
        text = _build_text(listing, fltr, analysis)
        photos = listing.photos or []

        for attempt in range(3):
            try:
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
                await asyncio.sleep(0.5)  # throttle to avoid flood limits
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception:
                break

    async def send_daily_stats(self, chat_id: int, stats: list[dict]) -> None:
        if not stats:
            await self._bot.send_message(
                chat_id=chat_id,
                text="📊 No new listings found today.",
            )
            return

        lines = ["📊 <b>Your stats for today</b>\n"]
        for s in stats:
            lines.append(f"🔍 <b>{s['filter_name']}</b>:")
            lines.append(f"— New listings: {s['count']}")
            if s.get("min_price"):
                lines.append(f"— Min price: {_fmt_price(s['min_price'])}")
            if s.get("avg_price"):
                lines.append(f"— Avg price: {_fmt_price(s['avg_price'])}")
            if s.get("best_url"):
                lines.append(f"— Best deal: <a href='{s['best_url']}'>link</a>")
            lines.append("")

        await self._bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
