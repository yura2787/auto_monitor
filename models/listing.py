from sqlalchemy import String, DateTime, Integer, ForeignKey, func, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    olx_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filter_id: Mapped[int] = mapped_column(
        ForeignKey("filters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    photos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    found_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filter: Mapped["Filter"] = relationship("Filter", back_populates="listings")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="listing", cascade="all, delete-orphan"
    )
