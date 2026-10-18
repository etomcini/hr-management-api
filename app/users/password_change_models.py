from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.dependencies.database import Base


class PasswordChangeHistory(Base):
    __tablename__ = "password_change_history"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Helps PostgreSQL efficiently find recent changes for a user.
    __table_args__ = (
        Index(
            "ix_password_change_history_user_changed",
            "user_id",
            "changed_at",
        ),
    )
