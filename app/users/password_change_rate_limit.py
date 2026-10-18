from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.users.password_change_models import PasswordChangeHistory


async def check_password_change_rate_limit(
    db: AsyncSession,
    user_id: int,
    now: datetime,
) -> None:
    # Calculate the beginning of the rolling time window.
    window_start = now - timedelta(minutes=settings.password_change_window_minutes)

    # Count successful password changes within the time window.
    stmt = select(func.count(PasswordChangeHistory.id)).where(
        PasswordChangeHistory.user_id == user_id,
        PasswordChangeHistory.changed_at > window_start,
    )

    count = await db.scalar(stmt)

    # Block the request if the user has reached the allowed limit.
    if count is not None and count >= settings.password_change_max_per_hour:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=("Password change limit reached. Please try again later."),
        )


def record_successful_password_change(
    db: AsyncSession,
    user_id: int,
    now: datetime,
) -> None:
    # Stage a successful password-change record in the current transaction.
    history = PasswordChangeHistory(
        user_id=user_id,
        changed_at=now,
    )

    db.add(history)

    # Do not commit here.
    # The password update, session revocation and history record
    # must all succeed or fail together.
