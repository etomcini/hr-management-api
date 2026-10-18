from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User
from app.users.password_change_models import PasswordChangeHistory
from app.users.password_change_rate_limit import check_password_change_rate_limit


@pytest.mark.integration
async def test_four_changes_within_one_hour_are_allowed(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Four existing changes should still be allowed until the limit is reached."""
    now = datetime.now(UTC)

    # Three previous successful password changes.
    for minutes_ago in (10, 20, 30):
        db_session.add(
            PasswordChangeHistory(
                user_id=test_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    # With three previous changes, the fourth is permitted.
    await check_password_change_rate_limit(
        db=db_session,
        user_id=test_user.id,
        now=now,
    )


@pytest.mark.integration
async def test_fifth_password_change_is_rejected(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """A fifth change within the rolling window must be rejected."""
    now = datetime.now(UTC)

    for minutes_ago in (5, 10, 20, 30):
        db_session.add(
            PasswordChangeHistory(
                user_id=test_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await check_password_change_rate_limit(
            db=db_session,
            user_id=test_user.id,
            now=now,
        )

    assert exc_info.value.status_code == 429


@pytest.mark.integration
async def test_change_allowed_after_rolling_window(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """History older than one hour must not count toward the limit."""
    now = datetime.now(UTC)

    for minutes_ago in (61, 10, 20, 30):
        db_session.add(
            PasswordChangeHistory(
                user_id=test_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    # Only three changes remain inside the one-hour window.
    await check_password_change_rate_limit(
        db=db_session,
        user_id=test_user.id,
        now=now,
    )


@pytest.mark.integration
async def test_rate_limit_is_per_user(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Another user's password changes must not affect this user."""
    from tests.factories.users import UserFactory

    other_user = UserFactory.build()
    db_session.add(other_user)
    await db_session.flush()

    now = datetime.now(UTC)

    # Fill the other user's allowance.
    for minutes_ago in (5, 10, 15, 20):
        db_session.add(
            PasswordChangeHistory(
                user_id=other_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    # Our test user has no history and should be allowed.
    await check_password_change_rate_limit(
        db=db_session,
        user_id=test_user.id,
        now=now,
    )


@pytest.mark.integration
async def test_history_count_matches_successful_changes(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Verify that history records can be counted for a specific user."""
    now = datetime.now(UTC)

    db_session.add(
        PasswordChangeHistory(
            user_id=test_user.id,
            changed_at=now,
        )
    )

    await db_session.flush()

    count = await db_session.scalar(
        select(func.count(PasswordChangeHistory.id)).where(
            PasswordChangeHistory.user_id == test_user.id
        )
    )

    assert count == 1
