import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from config.settings import settings


@dataclass
class OLXListing:
    olx_id: str
    title: str
    price: Optional[int]
    year: Optional[int]
    mileage: Optional[int]
    city: Optional[str]
    engine: Optional[str]
    url: str
    photos: list[str] = field(default_factory=list)
    published_at: Optional[str] = None


class OLXParser:
    BASE_URL = settings.OLX_BASE_URL

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    def _build_url(
        self,
        brand: str,
        model: Optional[str],
        year_from: Optional[int],
        year_to: Optional[int],
        price_from: Optional[int],
        price_to: Optional[int],
        mileage_from: Optional[int],
        mileage_to: Optional[int],
        condition: Optional[str],
    ) -> str:
        brand_slug = brand.lower().replace(" ", "-")
        url = f"{self.BASE_URL}?search[filter_enum_brand][]={brand_slug}"

        if model:
            url += f"&search[filter_enum_model][]={model.lower().replace(' ', '-')}"
        if year_from:
            url += f"&search[filter_float_year:from]={year_from}"
        if year_to:
            url += f"&search[filter_float_year:to]={year_to}"
        if price_from:
            url += f"&search[filter_float_price:from]={price_from}"
        if price_to:
            url += f"&search[filter_float_price:to]={price_to}"
        if mileage_from:
            url += f"&search[filter_float_mileage:from]={mileage_from * 1000}"
        if mileage_to:
            url += f"&search[filter_float_mileage:to]={mileage_to * 1000}"
        if condition == "new":
            url += "&search[filter_enum_state][]=new"
        elif condition == "used":
            url += "&search[filter_enum_state][]=used"
        elif condition == "damaged":
            url += "&search[filter_enum_state][]=damaged"

        return url

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    @staticmethod
    def _parse_mileage(text: str) -> Optional[int]:
        match = re.search(r"(\d[\d\s]*)", text)
        if match:
            return int(re.sub(r"\s", "", match.group(1)))
        return None

    async def _parse_listing_cards(self, page: Page) -> list[OLXListing]:
        listings: list[OLXListing] = []

        try:
            await page.wait_for_selector("[data-cy='l-card']", timeout=15000)
        except Exception:
            return listings

        cards = await page.query_selector_all("[data-cy='l-card']")

        for card in cards:
            try:
                link_el = await card.query_selector("a[href]")
                if not link_el:
                    continue
                url = await link_el.get_attribute("href") or ""
                if not url:
                    continue
                if not url.startswith("http"):
                    url = f"https://www.olx.ua{url}"

                # пропускаємо promoted / зовнішні посилання
                if "olx.ua" not in url:
                    continue

                match = re.search(r"-(\w{6,})\.html", url)
                if not match:
                    continue
                olx_id = match.group(1)

                title_el = await card.query_selector("h6, [data-cy='ad-card-title'] h6")
                title = (await title_el.inner_text()).strip() if title_el else "Без назви"

                price_el = await card.query_selector("[data-testid='ad-price']")
                price_text = (await price_el.inner_text()).strip() if price_el else ""
                price = self._parse_price(price_text)

                location_el = await card.query_selector("[data-testid='location-date']")
                location_text = (await location_el.inner_text()).strip() if location_el else ""
                loc_parts = [p.strip() for p in location_text.split("-")]
                city = loc_parts[0] if loc_parts else None
                published_at = loc_parts[-1] if len(loc_parts) > 1 else None

                photo_el = await card.query_selector("img[src]")
                photo_src = await photo_el.get_attribute("src") if photo_el else None
                photos = (
                    [photo_src]
                    if photo_src and "no-photo" not in photo_src
                    else []
                )

                listings.append(
                    OLXListing(
                        olx_id=olx_id,
                        title=title,
                        price=price,
                        year=None,
                        mileage=None,
                        city=city,
                        engine=None,
                        url=url,
                        photos=photos,
                        published_at=published_at,
                    )
                )
            except Exception:
                continue

        return listings

    async def _enrich(self, page: Page, listing: OLXListing) -> None:
        """Заходить на сторінку оголошення і витягує деталі + всі фото."""
        try:
            await page.goto(listing.url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_selector("[data-cy='ad_title']", timeout=10000)

            params = await page.query_selector_all("[data-testid='ad-parameters-item']")
            for param in params:
                text = (await param.inner_text()).strip()
                lower = text.lower()
                if "рік" in lower or "year" in lower:
                    m = re.search(r"(\d{4})", text)
                    if m:
                        listing.year = int(m.group(1))
                elif "пробіг" in lower or "mileage" in lower:
                    listing.mileage = self._parse_mileage(text)
                elif "двигун" in lower or "об'єм" in lower:
                    listing.engine = text.split(":")[-1].strip()

            photos: list[str] = []
            photo_els = await page.query_selector_all("[data-cy='ad-photo'] img, .swiper-slide img")
            for el in photo_els[: settings.PHOTOS_LIMIT]:
                src = await el.get_attribute("src")
                if src and "no-photo" not in src:
                    photos.append(src)
            if photos:
                listing.photos = photos

        except Exception:
            pass

    async def parse(
        self,
        brand: str,
        model: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        mileage_from: Optional[int] = None,
        mileage_to: Optional[int] = None,
        condition: Optional[str] = None,
        enrich: bool = True,
    ) -> list[OLXListing]:
        base_url = self._build_url(
            brand, model, year_from, year_to,
            price_from, price_to, mileage_from, mileage_to, condition,
        )
        browser = await self._ensure_browser()
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="uk-UA",
        )
        page = await context.new_page()
        all_listings: list[OLXListing] = []

        try:
            for page_num in range(1, settings.MAX_PAGES + 1):
                url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
                await page.goto(url, timeout=30000, wait_until="networkidle")

                page_listings = await self._parse_listing_cards(page)
                if not page_listings:
                    break

                all_listings.extend(page_listings)

                has_next = await page.query_selector("[data-cy='pagination-forward']")
                if not has_next:
                    break

                await asyncio.sleep(1.5)

            if enrich:
                for listing in all_listings:
                    await self._enrich(page, listing)
                    await asyncio.sleep(0.8)

        finally:
            await context.close()

        return all_listings

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
