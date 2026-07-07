import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config.settings import settings

# manual overrides for Ukrainian/Russian spellings → OLX slug
BRAND_ALIASES: dict[str, str] = {
    "тойота": "toyota", "бмв": "bmw", "мерседес": "mercedes-benz", "мерс": "mercedes-benz",
    "фольксваген": "volkswagen", "фольк": "volkswagen", "vw": "volkswagen",
    "ауді": "audi", "ауди": "audi", "хюндай": "hyundai", "хендай": "hyundai", "хундай": "hyundai",
    "кіа": "kia", "киа": "kia", "форд": "ford", "ніссан": "nissan", "нісан": "nissan",
    "хонда": "honda", "мазда": "mazda", "шевроле": "chevrolet", "шеві": "chevrolet",
    "шкода": "skoda", "рено": "renault", "пежо": "peugeot", "опель": "opel",
    "міцубісі": "mitsubishi", "міцу": "mitsubishi", "субару": "subaru", "лексус": "lexus",
    "ленд ровер": "land-rover", "лендровер": "land-rover", "рендж ровер": "land-rover",
    "джип": "jeep", "додж": "dodge", "порше": "porsche", "вольво": "volvo",
    "сеат": "seat", "фіат": "fiat", "сузукі": "suzuki", "деу": "daewoo", "део": "daewoo",
    "лада": "lada", "ваз": "lada", "жигулі": "lada", "джилі": "geely", "чері": "chery",
    "бід": "byd", "тесла": "tesla", "кадилак": "cadillac", "лінкольн": "lincoln",
    "крайслер": "chrysler", "міні": "mini", "смарт": "smart", "сітроен": "citroen",
    "дачія": "dacia", "мазераті": "maserati", "феррарі": "ferrari", "бентлі": "bentley",
    "ролс ройс": "rolls-royce", "астон мартін": "aston-martin", "хавал": "haval",
    "чанган": "changan", "заз": "zaz", "запорожець": "zaz", "москвич": "moskvich",
    "уаз": "uaz", "газ": "gaz", "волга": "gaz", "купра": "cupra", "інфініті": "infiniti",
    "акура": "acura", "генезис": "genesis",
}

# cache for dynamically loaded slugs from OLX
_BRAND_SLUGS_CACHE: dict[str, str] = {}


async def _load_brand_slugs() -> dict[str, str]:
    """Fetch all brand slugs from OLX category page."""
    global _BRAND_SLUGS_CACHE
    if _BRAND_SLUGS_CACHE:
        return _BRAND_SLUGS_CACHE
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.olx.ua/uk/transport/legkovye-avtomobili/",
                headers=HEADERS,
            )
        import re as _re
        slugs = _re.findall(r'href="/uk/transport/legkovye-avtomobili/([^/"]+)/"', resp.text)
        # slug → slug (exact match)
        _BRAND_SLUGS_CACHE = {s: s for s in slugs}
        # also map without dashes: "land-rover" → "land rover"
        for s in slugs:
            _BRAND_SLUGS_CACHE[s.replace("-", " ")] = s
    except Exception:
        pass
    return _BRAND_SLUGS_CACHE


# keep small static dict for backwards compat — used only as fallback
BRAND_SLUGS: dict[str, str] = {
    # Toyota
    "toyota": "toyota", "тойота": "toyota",
    # BMW
    "bmw": "bmw", "бмв": "bmw",
    # Mercedes
    "mercedes": "mercedes-benz", "мерседес": "mercedes-benz", "mercedes-benz": "mercedes-benz", "мерс": "mercedes-benz",
    # Volkswagen
    "volkswagen": "volkswagen", "фольксваген": "volkswagen", "vw": "volkswagen", "фольк": "volkswagen",
    # Audi
    "audi": "audi", "ауді": "audi", "ауди": "audi",
    # Hyundai
    "hyundai": "hyundai", "хюндай": "hyundai", "хундай": "hyundai", "хендай": "hyundai",
    # Kia
    "kia": "kia", "киа": "kia", "кіа": "kia",
    # Ford
    "ford": "ford", "форд": "ford",
    # Nissan
    "nissan": "nissan", "ніссан": "nissan", "нісан": "nissan", "нисан": "nissan",
    # Honda
    "honda": "honda", "хонда": "honda",
    # Mazda
    "mazda": "mazda", "мазда": "mazda",
    # Chevrolet
    "chevrolet": "chevrolet", "шевроле": "chevrolet", "шеві": "chevrolet",
    # Skoda
    "skoda": "skoda", "шкода": "skoda", "škoda": "skoda",
    # Renault
    "renault": "renault", "рено": "renault",
    # Peugeot
    "peugeot": "peugeot", "пежо": "peugeot",
    # Opel
    "opel": "opel", "опель": "opel",
    # Mitsubishi
    "mitsubishi": "mitsubishi", "міцубісі": "mitsubishi", "митсубиши": "mitsubishi", "міцу": "mitsubishi",
    # Subaru
    "subaru": "subaru", "субару": "subaru",
    # Lexus
    "lexus": "lexus", "лексус": "lexus",
    # Land Rover
    "land rover": "land-rover", "ленд ровер": "land-rover", "лендровер": "land-rover", "ленд-ровер": "land-rover",
    # Range Rover
    "range rover": "land-rover", "рендж ровер": "land-rover",
    # Jeep
    "jeep": "jeep", "джип": "jeep",
    # Dodge
    "dodge": "dodge", "додж": "dodge",
    # Porsche
    "porsche": "porsche", "порше": "porsche",
    # Volvo
    "volvo": "volvo", "вольво": "volvo",
    # Seat
    "seat": "seat", "сеат": "seat",
    # Fiat
    "fiat": "fiat", "фіат": "fiat",
    # Suzuki
    "suzuki": "suzuki", "сузукі": "suzuki", "сузуки": "suzuki",
    # Daewoo
    "daewoo": "daewoo", "деу": "daewoo", "део": "daewoo",
    # Lada / VAZ
    "lada": "lada", "лада": "lada", "ваз": "lada", "жигулі": "lada", "жигули": "lada",
    # Geely
    "geely": "geely", "джилі": "geely", "джили": "geely",
    # Chery
    "chery": "chery", "черрі": "chery", "чері": "chery",
    # BYD
    "byd": "byd", "бід": "byd",
    # Alfa Romeo
    "alfa romeo": "alfa-romeo", "альфа ромео": "alfa-romeo", "альфа-ромео": "alfa-romeo",
    # Acura
    "acura": "acura", "акура": "acura",
    # Infiniti
    "infiniti": "infiniti", "інфініті": "infiniti", "инфинити": "infiniti",
    # Tesla
    "tesla": "tesla", "тесла": "tesla",
    # Cadillac
    "cadillac": "cadillac", "кадилак": "cadillac",
    # Lincoln
    "lincoln": "lincoln", "лінкольн": "lincoln",
    # Buick
    "buick": "buick", "бьюік": "buick",
    # Chrysler
    "chrysler": "chrysler", "крайслер": "chrysler",
    # Jeep Grand Cherokee alias
    "grand cherokee": "jeep",
    # Mini
    "mini": "mini", "міні": "mini",
    # Smart
    "smart": "smart", "смарт": "smart",
    # Citroen
    "citroen": "citroen", "сітроен": "citroen", "citroën": "citroen",
    # Dacia
    "dacia": "dacia", "дачія": "dacia",
    # Lancia
    "lancia": "lancia", "ланча": "lancia",
    # Maserati
    "maserati": "maserati", "мазераті": "maserati",
    # Ferrari
    "ferrari": "ferrari", "феррарі": "ferrari",
    # Lamborghini
    "lamborghini": "lamborghini", "ламборгіні": "lamborghini",
    # Bentley
    "bentley": "bentley", "бентлі": "bentley",
    # Rolls-Royce
    "rolls-royce": "rolls-royce", "rolls royce": "rolls-royce", "ролс ройс": "rolls-royce",
    # Aston Martin
    "aston martin": "aston-martin", "астон мартін": "aston-martin",
    # Genesis
    "genesis": "genesis", "генезис": "genesis",
    # Haval
    "haval": "haval", "хавал": "haval",
    # Great Wall
    "great wall": "great-wall", "грейт вол": "great-wall",
    # Changan
    "changan": "changan", "чанган": "changan",
    # JAC
    "jac": "jac", "джак": "jac",
    # Foton
    "foton": "foton", "фотон": "foton",
    # ZAZ
    "zaz": "zaz", "заз": "zaz", "запорожець": "zaz",
    # Moskvich
    "moskvich": "moskvich", "москвич": "moskvich",
    # UAZ
    "uaz": "uaz", "уаз": "uaz",
    # GAZ
    "gaz": "gaz", "газ": "gaz", "волга": "gaz",
    # Cupra
    "cupra": "cupra", "купра": "cupra",
    # Lynk & Co
    "lynk": "lynk-co", "lynk & co": "lynk-co",
    # Ora
    "ora": "ora", "ора": "ora",
    # Zeekr
    "zeekr": "zeekr", "зікр": "zeekr",
    # Nio
    "nio": "nio", "ніо": "nio",
    # Xpeng
    "xpeng": "xpeng", "хпенг": "xpeng",
    # Li Auto
    "li auto": "li-auto", "лі авто": "li-auto",
}


async def normalize_brand(brand: str) -> str:
    from difflib import get_close_matches
    key = brand.strip().lower()

    # 1. manual alias (Ukrainian/Russian spelling)
    if key in BRAND_ALIASES:
        return BRAND_ALIASES[key]

    # 2. exact match in dynamic OLX slugs
    slugs = await _load_brand_slugs()
    if key in slugs:
        return slugs[key]

    # 3. fuzzy match against OLX slugs + aliases
    all_keys = list(slugs.keys()) + list(BRAND_ALIASES.keys())
    matches = get_close_matches(key, all_keys, n=1, cutoff=0.72)
    if matches:
        best = matches[0]
        return BRAND_ALIASES.get(best) or slugs.get(best, best)

    return key.replace(" ", "-")


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


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class OLXParser:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=30,
            )
        return self._client

    async def _build_url(
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
        brand_slug = await normalize_brand(brand)
        base = f"https://www.olx.ua/uk/transport/legkovye-avtomobili/{brand_slug}/"

        if model:
            model_slug = model.lower().replace(" ", "-")
            base += f"{model_slug}/"

        params: list[str] = []

        if year_from:
            params.append(f"search[filter_float_year:from]={year_from}")
        if year_to:
            params.append(f"search[filter_float_year:to]={year_to}")
        if price_from:
            params.append(f"search[filter_float_price:from]={price_from}")
        if price_to:
            params.append(f"search[filter_float_price:to]={price_to}")
        if mileage_from:
            params.append(f"search[filter_float_mileage:from]={mileage_from * 1000}")
        if mileage_to:
            params.append(f"search[filter_float_mileage:to]={mileage_to * 1000}")
        if condition == "new":
            params.append("search[filter_enum_state][0]=new")
        elif condition == "used":
            params.append("search[filter_enum_state][0]=used")
        elif condition == "damaged":
            params.append("search[filter_enum_state][0]=damaged")

        return f"{base}?{'&'.join(params)}" if params else base

    @staticmethod
    def _parse_price(text: str) -> Optional[int]:
        text = text.strip()
        # extract numeric value ignoring spaces/dots used as thousand separators
        match = re.search(r"[\d\s.,]+", text)
        if not match:
            return None
        raw = match.group(0)
        # remove spaces and handle comma/dot as decimal separator
        raw = raw.replace(" ", "").replace("\xa0", "")
        # if price has decimal part (e.g. 198097.43) — take integer part only
        raw = re.sub(r"[.,]\d{1,2}$", "", raw)
        raw = re.sub(r"[.,]", "", raw)
        value = int(raw) if raw.isdigit() else None
        if value is None:
            return None
        # convert UAH to USD (approximate rate)
        if "грн" in text.lower() or value > 100_000:
            value = int(value / 42)
        return value

    def _parse_cards(self, html: str) -> list[OLXListing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        listings: list[OLXListing] = []

        for card in cards:
            try:
                link = card.find("a", href=True)
                if not link:
                    continue
                url = link["href"]
                if not url.startswith("http"):
                    url = f"https://www.olx.ua{url}"
                if "olx.ua" not in url:
                    continue

                match = re.search(r"-(\w{6,})\.html", url)
                if not match:
                    continue
                olx_id = match.group(1)

                title_el = card.find(attrs={"data-testid": "ad-card-title"})
                title = title_el.get_text(strip=True) if title_el else "No title"

                price_el = card.find(attrs={"data-testid": "ad-price"})
                price = self._parse_price(price_el.get_text()) if price_el else None

                location_el = card.find(attrs={"data-testid": "location-date"})
                city, published_at = None, None
                if location_el:
                    parts = [p.strip() for p in location_el.get_text().split("-")]
                    city = parts[0] if parts else None
                    published_at = parts[-1] if len(parts) > 1 else None

                img = card.find("img", src=True)
                photos = []
                if img and "no-photo" not in img["src"]:
                    photos = [img["src"]]

                listings.append(OLXListing(
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
                ))
            except Exception:
                continue

        return listings

    async def _enrich(self, client: httpx.AsyncClient, listing: OLXListing) -> None:
        try:
            resp = await client.get(listing.url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")

            for li in soup.find_all("li", class_=re.compile("param")):
                text = li.get_text(" ", strip=True).lower()
                if "рік" in text:
                    m = re.search(r"(\d{4})", text)
                    if m:
                        listing.year = int(m.group(1))
                elif "пробіг" in text:
                    m = re.search(r"(\d[\d\s]*)", text)
                    if m:
                        listing.mileage = int(re.sub(r"\s", "", m.group(1)))
                elif "двигун" in text or "об'єм" in text:
                    listing.engine = text.split(":")[-1].strip()

            imgs = soup.find_all("img", attrs={"data-cy": re.compile("ad-photo")})
            photos = [i["src"] for i in imgs if i.get("src") and "no-photo" not in i["src"]]
            if photos:
                listing.photos = photos[: settings.PHOTOS_LIMIT]

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
        base_url = await self._build_url(
            brand, model, year_from, year_to,
            price_from, price_to, mileage_from, mileage_to, condition,
        )
        client = await self._get_client()
        all_listings: list[OLXListing] = []

        for page_num in range(1, settings.MAX_PAGES + 1):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page_num == 1 else f"{base_url}{sep}page={page_num}"

            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception:
                break

            page_listings = self._parse_cards(resp.text)
            if not page_listings:
                break

            all_listings.extend(page_listings)
            await asyncio.sleep(1)

        if enrich:
            for listing in all_listings:
                await self._enrich(client, listing)
                await asyncio.sleep(0.5)

        return all_listings

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
