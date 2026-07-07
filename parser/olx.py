import asyncio
import re
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Optional

import httpx

from config.settings import settings


BRAND_ALIASES: dict[str, str] = {
    "тойота": "toyota", "тйота": "toyota", "тоёта": "toyota",
    "ауді": "audi", "ауди": "audi",
    "бмв": "bmw",
    "мерседес": "mercedes-benz", "мерс": "mercedes-benz",
    "mercedes": "mercedes-benz", "mercedes benz": "mercedes-benz",
    "фольксваген": "volkswagen", "фольцваген": "volkswagen", "vw": "volkswagen",
    "шкода": "skoda",
    "рено": "renault",
    "пежо": "peugeot",
    "форд": "ford",
    "хонда": "honda",
    "хюндай": "hyundai", "хундай": "hyundai", "хендай": "hyundai",
    "кіа": "kia", "киа": "kia",
    "нісан": "nissan", "нисан": "nissan",
    "міцубісі": "mitsubishi", "міцу": "mitsubishi",
    "субару": "subaru",
    "мазда": "mazda",
    "лексус": "lexus",
    "інфініті": "infiniti",
    "жигуль": "lada", "жигулі": "lada", "ваз": "lada", "лада": "lada",
    "волга": "gaz", "газ": "gaz",
    "москвич": "moskvich",
    "опель": "opel",
    "сеат": "seat",
    "чері": "chery",
    "джилі": "geely",
    "хавал": "haval",
    "чанган": "changan",
    "бід": "byd", "бйд": "byd",
    "тесла": "tesla",
    "вольво": "volvo",
    "джип": "jeep",
    "шевроле": "chevrolet", "шеві": "chevrolet",
    "додж": "dodge",
    "порше": "porsche",
    "заз": "zaz", "запорожець": "zaz",
    "уаз": "uaz",
    "акура": "acura",
    "генезис": "genesis",
    "купра": "cupra",
    "фіат": "fiat",
    "сузукі": "suzuki",
    "деу": "daewoo", "део": "daewoo",
    "ленд ровер": "land-rover", "лендровер": "land-rover",
    "міні": "mini",
    "сітроен": "citroen",
    "дачія": "dacia",
}

_brand_slugs: list[str] = []


async def _load_brand_slugs() -> list[str]:
    global _brand_slugs
    if _brand_slugs:
        return _brand_slugs
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://www.olx.ua/uk/transport/legkovye-avtomobili/",
                headers={"User-Agent": "Mozilla/5.0"},
            )
        slugs = re.findall(r'/legkovye-avtomobili/([^/"]+)/', r.text)
        _brand_slugs = sorted(set(slugs))
    except Exception:
        pass
    return _brand_slugs


async def normalize_brand(raw: str) -> str:
    lower = raw.strip().lower()
    if lower in BRAND_ALIASES:
        return BRAND_ALIASES[lower]
    slugs = await _load_brand_slugs()
    # filter out slugs that look like dealer pages (contain digits or start with q-)
    clean_slugs = [s for s in slugs if not s.startswith("q-") and not any(c.isdigit() for c in s)]
    if lower in clean_slugs:
        return lower
    matches = get_close_matches(lower, list(BRAND_ALIASES.keys()) + clean_slugs, n=1, cutoff=0.72)
    if matches:
        candidate = matches[0]
        return BRAND_ALIASES.get(candidate, candidate)
    return lower.replace(" ", "-")


@dataclass
class OLXListing:
    olx_id: str
    title: str
    price: Optional[int]       # USD
    year: Optional[int]
    mileage: Optional[int]     # thousands km
    city: Optional[str]
    engine: Optional[str]
    url: str
    photos: list[str] = field(default_factory=list)
    published_at: Optional[str] = None


# OLX API car state type → our condition values
_CONDITION_MAP = {
    "new": "filter_enum_car_state_type][0]=new",
    "used": "with_mileage",
    "damaged": "damaged",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

OLX_API = "https://www.olx.ua/api/v1/offers/"
CATEGORY_ID = 108  # legkovye-avtomobili


class OLXParser:

    async def parse(
        self,
        brand: str,
        model: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        price_from: Optional[int] = None,   # USD
        price_to: Optional[int] = None,     # USD
        mileage_from: Optional[int] = None, # k km
        mileage_to: Optional[int] = None,   # k km
        condition: Optional[str] = None,
        enrich: bool = True,                # kept for API compat, ignored (API returns full data)
    ) -> list[OLXListing]:
        brand_slug = await normalize_brand(brand)
        model_slug = model.lower().replace(" ", "-") if model else None

        params: dict = {
            "offset": 0,
            "limit": 50,
            "category_id": CATEGORY_ID,
            "sort_by": "created_at:desc",
            "filter[filter_enum_brand][0]": brand_slug,
        }
        if model_slug:
            params["filter[filter_enum_model][0]"] = model_slug

        # Price filter in USD (OLX API accepts USD directly)
        if price_from:
            params["filter[filter_float_price:from]"] = price_from
        if price_to:
            params["filter[filter_float_price:to]"] = price_to

        # Condition
        if condition == "new":
            params["filter[filter_enum_car_state_type][0]"] = "new"
        elif condition == "damaged":
            params["filter[filter_enum_car_state_type][0]"] = "damaged"
        elif condition == "used":
            params["filter[filter_enum_car_state_type][0]"] = "with_mileage"

        all_listings: list[OLXListing] = []

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
            for page in range(settings.MAX_PAGES):
                params["offset"] = page * 50
                try:
                    # Build query string manually — httpx percent-encodes [] which OLX doesn't accept
                    qs = "&".join(f"{k}={v}" for k, v in params.items())
                    r = await client.get(f"{OLX_API}?{qs}")
                    data = r.json()
                except Exception:
                    break

                offers = data.get("data", [])
                if not offers:
                    break

                for offer in offers:
                    listing = self._parse_offer(offer)
                    if listing is None:
                        continue

                    # Brand check — API mixes in promoted listings from other brands.
                    # Build accepted names: Latin slug + all Ukrainian aliases for this brand.
                    _brand_names = {brand_slug.split("-")[0]}
                    for _ukr, _lat in BRAND_ALIASES.items():
                        if _lat == brand_slug:
                            _brand_names.add(_ukr.split()[0])  # first word of alias
                    _title_lower = listing.title.lower()
                    if not any(name in _title_lower for name in _brand_names):
                        continue

                    # Model check — if model specified, verify it appears in title
                    if model_slug:
                        # use first word longer than 2 chars (handles "e-class" → "class", "x5" → "x5")
                        _model_words = [w for w in model_slug.split("-") if len(w) > 2]
                        _model_check = _model_words[0] if _model_words else model_slug
                        if _model_check not in _title_lower:
                            continue

                    # Year filter — skip listings with no year when filter is set
                    if year_from:
                        if not listing.year or listing.year < year_from:
                            continue
                    if year_to:
                        if not listing.year or listing.year > year_to:
                            continue

                    # Mileage filter — skip listings with no mileage when filter is set
                    if mileage_from:
                        if not listing.mileage or listing.mileage < mileage_from:
                            continue
                    if mileage_to:
                        if not listing.mileage or listing.mileage > mileage_to:
                            continue

                    all_listings.append(listing)

                await asyncio.sleep(0.5)

        return all_listings

    def _parse_offer(self, offer: dict) -> Optional[OLXListing]:
        try:
            olx_id = str(offer["id"])
            title = offer.get("title", "No title")
            url = offer.get("url", "")
            if not url.startswith("http"):
                url = f"https://www.olx.ua{url}"

            # extract params dict
            raw_params = {p["key"]: p["value"] for p in offer.get("params", [])}

            # price can be USD or UAH — normalize to USD
            price_info = raw_params.get("price", {})
            price_val = price_info.get("value")
            price_currency = price_info.get("currency", "USD")
            if isinstance(price_val, (int, float)) and price_val > 0:
                price = int(price_val) if price_currency == "USD" else int(price_val) // 42
            else:
                price = None

            # year
            year_val = raw_params.get("motor_year", {}).get("key")
            year = int(year_val) if year_val and str(year_val).isdigit() else None

            # mileage (in thousands km)
            mil_val = raw_params.get("motor_mileage_thou", {}).get("key")
            mileage = int(mil_val) if mil_val and str(mil_val).isdigit() else None

            # engine
            eng_val = raw_params.get("motor_engine_size_litre", {}).get("key")
            engine = f"{eng_val} л" if eng_val else None

            # city
            city = offer.get("location", {}).get("city", {}).get("name")

            # published_at
            published_at = offer.get("last_refresh_time", "")[:10] if offer.get("last_refresh_time") else None

            # photos — replace size placeholder with actual size
            photos: list[str] = []
            for ph in offer.get("photos", [])[:settings.PHOTOS_LIMIT]:
                link = ph.get("link", "")
                if link:
                    photos.append(link.replace("{width}x{height}", "800x600"))

            return OLXListing(
                olx_id=olx_id,
                title=title,
                price=price,
                year=year,
                mileage=mileage,
                city=city,
                engine=engine,
                url=url,
                photos=photos,
                published_at=published_at,
            )
        except Exception:
            return None

    async def close(self) -> None:
        pass
