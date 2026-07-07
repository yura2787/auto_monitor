import statistics
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from config.settings import settings

if TYPE_CHECKING:
    from parser.olx import OLXParser


@dataclass
class PriceAnalysis:
    verdict: str
    emoji: str
    median_price: int
    sample_size: int
    diff_percent: float


class PriceAnalyzer:
    def __init__(self, parser: "OLXParser") -> None:
        self._parser = parser

    async def get_market_median(
        self,
        brand: str,
        model: Optional[str],
    ) -> Optional[int]:
        """Fetch market listings once and return median price in USD."""
        try:
            market_listings = await self._parser.parse(
                brand=brand,
                model=model,
                enrich=False,
            )
        except Exception:
            return None

        prices = [
            lst.price
            for lst in market_listings
            if lst.price and lst.price > 500
        ][: settings.MARKET_SAMPLE_SIZE]

        if len(prices) < 5:
            return None

        return int(statistics.median(prices))

    def compare(self, current_price: int, median_price: int, sample_size: int) -> PriceAnalysis:
        """Compare a single price against pre-fetched market median."""
        diff = (current_price - median_price) / median_price * 100

        if diff <= -20:
            emoji, verdict = "💚", f"Excellent — {abs(round(diff))}% below market"
        elif diff <= -10:
            emoji, verdict = "✅", f"Good — {abs(round(diff))}% below market"
        elif diff < 15:
            emoji, verdict = "😐", "Market price"
        else:
            emoji, verdict = "⚠️", f"Above market by {round(diff)}%"

        return PriceAnalysis(
            verdict=verdict,
            emoji=emoji,
            median_price=median_price,
            sample_size=sample_size,
            diff_percent=round(diff, 1),
        )

    async def analyze(
        self,
        brand: str,
        model: Optional[str],
        current_price: int,
    ) -> Optional[PriceAnalysis]:
        """Legacy single-call API — fetches market data each time. Use get_market_median + compare instead."""
        median = await self.get_market_median(brand, model)
        if median is None:
            return None
        return self.compare(current_price, median, 0)
