from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.listing import Listing


class DuplicateChecker:
    async def is_duplicate(self, session: AsyncSession, olx_id: str, filter_id: int) -> bool:
        result = await session.execute(
            select(Listing.id)
            .where(Listing.olx_id == olx_id, Listing.filter_id == filter_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def save(self, session: AsyncSession, listing: Listing) -> None:
        session.add(listing)
        await session.commit()
        await session.refresh(listing)
