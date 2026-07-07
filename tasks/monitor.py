import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete

from models.base import AsyncSessionLocal
from models.filter import Filter
from models.listing import Listing
from models.price_history import PriceHistory
from models.user import User
from parser.olx import OLXParser, OLXListing
from services.duplicate_checker import DuplicateChecker
from services.notifier import Notifier
from services.price_analyzer import PriceAnalyzer
from config.settings import settings
from tasks.celery_app import celery_app

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

logger = logging.getLogger(__name__)


def _make_bot() -> Bot:
    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )


async def _process_filter(
    fltr: Filter,
    parser: OLXParser,
    checker: DuplicateChecker,
    analyzer: PriceAnalyzer,
    notifier: Notifier,
) -> int:
    """Parse one filter, deduplicate, analyze price, notify. Returns count of new listings sent."""
    listings: list[OLXListing] = await parser.parse(
        brand=fltr.brand,
        model=fltr.model,
        year_from=fltr.year_from,
        year_to=fltr.year_to,
        price_from=fltr.price_from,
        price_to=fltr.price_to,
        mileage_from=fltr.mileage_from,
        mileage_to=fltr.mileage_to,
        condition=fltr.condition,
        enrich=True,
    )

    sent = 0
    async with AsyncSessionLocal() as session:
        for raw in listings:
            if await checker.is_duplicate(session, raw.olx_id, fltr.id):
                continue

            # save to DB before sending so we never double-notify on crash
            db_listing = Listing(
                olx_id=raw.olx_id,
                filter_id=fltr.id,
                title=raw.title,
                price=raw.price,
                year=raw.year,
                mileage=raw.mileage,
                city=raw.city,
                engine=raw.engine,
                url=raw.url,
                photos=raw.photos,
                published_at=raw.published_at,
            )
            await checker.save(session, db_listing)

            # record price history entry
            if raw.price:
                session.add(PriceHistory(listing_id=db_listing.id, price=raw.price))
                await session.commit()

            # price analysis against market
            analysis = None
            if raw.price:
                analysis = await analyzer.analyze(fltr.brand, fltr.model, raw.price)

            # fetch owner telegram_id via filter → user join
            user_result = await session.execute(
                select(User.telegram_id)
                .join(Filter, Filter.user_id == User.id)
                .where(Filter.id == fltr.id)
            )
            telegram_id = user_result.scalar_one_or_none()
            if telegram_id:
                await notifier.send_listing(telegram_id, raw, fltr, analysis)
                sent += 1

    return sent


async def _run_monitor_filters() -> None:
    parser = OLXParser()
    checker = DuplicateChecker()
    bot = _make_bot()
    notifier = Notifier(bot)
    analyzer = PriceAnalyzer(parser)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Filter).where(Filter.is_active == True)  # noqa: E712
            )
            active_filters = list(result.scalars().all())

        logger.info("Checking %d active filters", len(active_filters))

        for fltr in active_filters:
            try:
                count = await _process_filter(fltr, parser, checker, analyzer, notifier)
                logger.info("Filter %d (%s): %d new listings sent", fltr.id, fltr.display_name(), count)
            except Exception:
                logger.exception("Error processing filter %d", fltr.id)

    finally:
        await parser.close()
        await bot.session.close()


async def _run_daily_stats() -> None:
    bot = _make_bot()
    notifier = Notifier(bot)

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        async with AsyncSessionLocal() as session:
            users_result = await session.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = list(users_result.scalars().all())

            for user in users:
                filters_result = await session.execute(
                    select(Filter).where(Filter.user_id == user.id)
                )
                filters = list(filters_result.scalars().all())

                stats: list[dict] = []
                for fltr in filters:
                    rows = (await session.execute(
                        select(Listing).where(
                            Listing.filter_id == fltr.id,
                            Listing.found_at >= today_start,
                        )
                    )).scalars().all()

                    if not rows:
                        continue

                    prices = [r.price for r in rows if r.price]
                    best = min(rows, key=lambda r: r.price or 999_999_999)

                    stats.append({
                        "filter_name": fltr.display_name(),
                        "count": len(rows),
                        "min_price": min(prices) if prices else None,
                        "avg_price": int(sum(prices) / len(prices)) if prices else None,
                        "best_url": best.url,
                    })

                await notifier.send_daily_stats(user.telegram_id, stats)

    finally:
        await bot.session.close()


async def _run_cleanup() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.CLEANUP_DAYS)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(Listing).where(Listing.found_at < cutoff)
        )
        await session.commit()
        logger.info("Cleanup: removed %d old listings", result.rowcount)


async def _run_seed_filter(filter_id: int) -> None:
    """Parse OLX for a newly created filter and mark all current listings as seen.

    This prevents a flood of notifications on first monitor run.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Filter).where(Filter.id == filter_id))
        fltr = result.scalar_one_or_none()
        if not fltr:
            return

    parser = OLXParser()
    checker = DuplicateChecker()
    try:
        listings = await parser.parse(
            brand=fltr.brand,
            model=fltr.model,
            year_from=fltr.year_from,
            year_to=fltr.year_to,
            price_from=fltr.price_from,
            price_to=fltr.price_to,
            mileage_from=fltr.mileage_from,
            mileage_to=fltr.mileage_to,
            condition=fltr.condition,
            enrich=False,  # no need for details, just collect IDs
        )
        async with AsyncSessionLocal() as session:
            for raw in listings:
                if not await checker.is_duplicate(session, raw.olx_id, fltr.id):
                    db_listing = Listing(
                        olx_id=raw.olx_id,
                        filter_id=fltr.id,
                        title=raw.title,
                        price=raw.price,
                        year=None,
                        mileage=None,
                        city=raw.city,
                        engine=None,
                        url=raw.url,
                        photos=[],
                        published_at=raw.published_at,
                    )
                    await checker.save(session, db_listing)
        logger.info("Seeded filter %d with %d listings", filter_id, len(listings))
    finally:
        await parser.close()


# ── Celery tasks ──────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.monitor.monitor_filters", bind=True, max_retries=3)
def monitor_filters(self) -> None:
    try:
        asyncio.run(_run_monitor_filters())
    except Exception as exc:
        logger.exception("monitor_filters failed")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="tasks.monitor.daily_stats")
def daily_stats() -> None:
    asyncio.run(_run_daily_stats())


@celery_app.task(name="tasks.monitor.cleanup_old_listings")
def cleanup_old_listings() -> None:
    asyncio.run(_run_cleanup())


@celery_app.task(name="tasks.monitor.seed_filter")
def seed_filter(filter_id: int) -> None:
    asyncio.run(_run_seed_filter(filter_id))
