from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.users.models import User
from app.users.password_change_models import PasswordChangeHistory

PASSWORD = "TestPassword123!"


async def get_change_count(
    db: AsyncSession,
    user_id: int,
) -> int:
    """Count all recorded successful password changes for one user."""
    result = await db.scalar(
        select(func.count(PasswordChangeHistory.id)).where(
            PasswordChangeHistory.user_id == user_id
        )
    )
    return result or 0


@pytest.mark.api
async def test_successful_password_change(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    login_as,
) -> None:
    """A successful change updates the hash and creates one history entry."""
    headers = await login_as(test_user)

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 204, response.text

    await db_session.refresh(test_user)

    assert verify_password("NewPassword123!", test_user.password_hash)
    assert await get_change_count(db_session, test_user.id) == 1


@pytest.mark.api
async def test_incorrect_current_password_does_not_count(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    login_as,
) -> None:
    """Failed validation must not consume the user's allowance."""
    headers = await login_as(test_user)

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 400
    assert await get_change_count(db_session, test_user.id) == 0


@pytest.mark.api
async def test_same_password_does_not_count(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    login_as,
) -> None:
    """Reusing the current password must not create a history entry."""
    headers = await login_as(test_user)

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": PASSWORD,
        },
    )

    assert response.status_code == 400
    assert await get_change_count(db_session, test_user.id) == 0


@pytest.mark.api
async def test_fifth_password_change_returns_429(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    login_as,
) -> None:
    """A user with four recent changes must receive HTTP 429."""
    headers = await login_as(test_user)

    now = datetime.now(UTC)

    # Seed four previous successful changes.
    for minutes_ago in (5, 10, 15, 20):
        db_session.add(
            PasswordChangeHistory(
                user_id=test_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 429
    assert await get_change_count(db_session, test_user.id) == 4

    await db_session.refresh(test_user)

    # The rejected request must not modify the password.
    assert verify_password(PASSWORD, test_user.password_hash)


@pytest.mark.api
async def test_password_change_revokes_current_session(
    client: AsyncClient,
    test_user: User,
    login_as,
) -> None:
    """The old access token must stop working after a password change."""
    headers = await login_as(test_user)

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 204, response.text

    # Reuse the same access token after its session was revoked.
    me_response = await client.get(
        "/api/v1/auth/me",
        headers=headers,
    )

    assert me_response.status_code == 401


@pytest.mark.api
async def test_four_successful_changes_then_fifth_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Four successful changes are allowed; the fifth is rejected."""

    passwords = [
        PASSWORD,
        "PasswordChange1!",
        "PasswordChange2!",
        "PasswordChange3!",
        "PasswordChange4!",
        "PasswordChange5!",
    ]

    # Four successful password changes.
    for index in range(4):
        login_response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": test_user.email,
                "password": passwords[index],
            },
        )

        assert login_response.status_code == 200, login_response.text

        access_token = login_response.json()["access_token"]

        response = await client.patch(
            "/api/v1/users/me/password",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "current_password": passwords[index],
                "new_password": passwords[index + 1],
            },
        )

        assert response.status_code == 204, response.text

    # Authenticate again using the fourth new password.
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": passwords[4],
        },
    )

    assert login_response.status_code == 200, login_response.text

    # Attempt the fifth password change.
    response = await client.patch(
        "/api/v1/users/me/password",
        headers={
            "Authorization": (f"Bearer {login_response.json()['access_token']}"),
        },
        json={
            "current_password": passwords[4],
            "new_password": passwords[5],
        },
    )

    assert response.status_code == 429

    await db_session.refresh(test_user)

    # Fourth password remains valid.
    assert verify_password(passwords[4], test_user.password_hash)

    # Exactly four successful changes were recorded.
    assert await get_change_count(db_session, test_user.id) == 4


@pytest.mark.api
async def test_rejected_change_preserves_existing_session(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    login_as,
) -> None:
    """Rate-limited changes must not revoke the user's current session."""

    headers = await login_as(test_user)

    now = datetime.now(UTC)

    # Simulate four successful password changes.
    for minutes_ago in (5, 10, 15, 20):
        db_session.add(
            PasswordChangeHistory(
                user_id=test_user.id,
                changed_at=now - timedelta(minutes=minutes_ago),
            )
        )

    await db_session.flush()

    # The fifth change should be rejected.
    response = await client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": "TestPassword123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 429

    # The current session must still be valid.
    me_response = await client.get(
        "/api/v1/auth/me",
        headers=headers,
    )

    assert me_response.status_code == 200


@pytest.mark.api
async def test_password_change_revokes_all_sessions(
    client: AsyncClient,
    test_user: User,
) -> None:
    """Changing the password must invalidate all existing sessions."""

    async def login(password: str) -> dict[str, str]:
        response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": test_user.email,
                "password": password,
            },
        )

        assert response.status_code == 200, response.text

        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    # Create two independent sessions for the same user.
    session_a = await login("TestPassword123!")
    session_b = await login("TestPassword123!")

    # Change the password from session A.
    response = await client.patch(
        "/api/v1/users/me/password",
        headers=session_a,
        json={
            "current_password": "TestPassword123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 204, response.text

    # Both previously issued access tokens must be invalid.
    response_a = await client.get("/api/v1/auth/me", headers=session_a)
    response_b = await client.get("/api/v1/auth/me", headers=session_b)

    assert response_a.status_code == 401
    assert response_b.status_code == 401

    # The new password must allow a fresh login.
    new_session = await login("NewPassword123!")

    response = await client.get(
        "/api/v1/auth/me",
        headers=new_session,
    )

    assert response.status_code == 200
