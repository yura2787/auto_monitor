from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="filters")
    listings: Mapped[list["Listing"]] = relationship(
        "Listing", back_populates="filter", cascade="all, delete-orphan"
    )

    def display_name(self) -> str:
        name = self.brand
        if self.model:
            name += f" {self.model}"
        if self.year_from and self.year_to:
            name += f" ({self.year_from}–{self.year_to})"
        elif self.year_from:
            name += f" ({self.year_from}+)"
        return name
