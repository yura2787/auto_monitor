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

    async def analyze(
        self,
        brand: str,
        model: Optional[str],
        current_price: int,
    ) -> Optional[PriceAnalysis]:
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

        median = int(statistics.median(prices))
        diff = (current_price - median) / median * 100

        if diff <= -20:
            emoji = "💚"
            verdict = f"Excellent price — {abs(round(diff))}% below market"
        elif diff <= -10:
            emoji = "✅"
            verdict = f"Good price — {abs(round(diff))}% below market"
        elif diff < 15:
            emoji = "😐"
            verdict = "Market price"
        else:
            emoji = "⚠️"
            verdict = f"Above market by {round(diff)}%"

        return PriceAnalysis(
            verdict=verdict,
            emoji=emoji,
            median_price=median,
            sample_size=len(prices),
            diff_percent=round(diff, 1),
        )
