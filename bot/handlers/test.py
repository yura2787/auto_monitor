import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bs4 import BeautifulSoup

from parser.olx import OLXParser
from services.price_analyzer import PriceAnalyzer
from services.notifier import Notifier

router = Router()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9",
}


@router.message(Command("test"))
async def cmd_test(message: Message) -> None:
    await message.answer("🔍 Parsing OLX, please wait...")

    parser = OLXParser()
    notifier = Notifier(message.bot)
    analyzer = PriceAnalyzer(parser)

    try:
        listings = await parser.parse(brand="Toyota", model="Camry", enrich=True)

        if not listings:
            await message.answer("❌ No listings found. Try /debug")
            return

        listing = listings[0]
        analysis = None
        if listing.price:
            analysis = await analyzer.analyze("Toyota", "Camry", listing.price)

        await notifier.send_listing(
            chat_id=message.chat.id,
            listing=listing,
            fltr=None,
            analysis=analysis,
        )
        await message.answer(f"✅ Done. Total found: {len(listings)}")

    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        await parser.close()


@router.message(Command("debug"))
async def cmd_debug(message: Message) -> None:
    """Fetches OLX HTML and reports how many listings were found."""
    await message.answer("🔍 Fetching OLX HTML...")

    url = "https://www.olx.ua/uk/transport/legkovye-avtomobili/toyota/camry/"
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})

        first_title = None
        if cards:
            title_el = cards[0].find(attrs={"data-testid": "ad-card-title"})
            first_title = title_el.get_text(strip=True) if title_el else "—"

        await message.answer(
            f"📄 Status: {resp.status_code}\n"
            f"🔗 URL: {url}\n"
            f"🃏 Cards found: {len(cards)}\n"
            f"📌 First title: {first_title or '—'}"
        )
    except Exception as e:
        await message.answer(f"❌ Debug error: {e}")
