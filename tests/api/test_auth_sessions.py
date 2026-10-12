from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken
from app.core.config import settings
from app.core.security import create_refresh_token
from app.users.models import User
from tests.factories.users import UserFactory

AUTH_URL = "/api/v1/auth"
TEST_PASSWORD = "TestPassword123!"


async def login_user(
    client: AsyncClient,
    user: User,
) -> dict[str, str]:
    response = await client.post(
        f"{AUTH_URL}/token",
        data={
            "username": user.email,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    return response.json()


async def refresh_token_request(
    client: AsyncClient,
    token: str,
):
    return await client.post(
        f"{AUTH_URL}/token/refresh",
        json={"refresh_token": token},
    )


async def get_session(
    db_session: AsyncSession,
    token: str,
) -> RefreshToken:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.algorithm],
    )

    session = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.jti == payload["jti"])
    )

    assert session is not None
    return session


@pytest.mark.api
async def test_refresh_valid_token(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    response = await refresh_token_request(client, tokens["refresh_token"])

    assert response.status_code == 200

    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert "refresh_token" not in data

    me_response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["id"] == test_user.id


@pytest.mark.api
async def test_refresh_expired_jwt(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    tokens = await login_user(client, test_user)
    session = await get_session(db_session, tokens["refresh_token"])

    expired_token = create_refresh_token(
        data={"sub": str(test_user.id)},
        jti=session.jti,
        expires_delta=timedelta(seconds=-60),
    )

    response = await refresh_token_request(client, expired_token)

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.parametrize(
    "invalid_token",
    [
        "invalid-token",
        "abc.def.ghi",
        "",
    ],
)
async def test_refresh_malformed_token(
    client: AsyncClient,
    invalid_token: str,
) -> None:
    response = await refresh_token_request(client, invalid_token)

    assert response.status_code == 401


@pytest.mark.api
async def test_access_token_cannot_refresh(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    response = await refresh_token_request(client, tokens["access_token"])

    assert response.status_code == 401


@pytest.mark.api
async def test_refresh_invalid_signature(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    payload = jwt.decode(
        tokens["refresh_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.algorithm],
    )

    forged_token = jwt.encode(
        payload,
        "incorrect-test-signing-key-with-at-least-32-bytes",
        algorithm=settings.algorithm,
    )

    response = await refresh_token_request(client, forged_token)

    assert response.status_code == 401


@pytest.mark.api
async def test_refresh_expired_database_session(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    tokens = await login_user(client, test_user)
    session = await get_session(db_session, tokens["refresh_token"])

    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    response = await refresh_token_request(client, tokens["refresh_token"])

    assert response.status_code == 401


@pytest.mark.api
async def test_logout_revokes_session(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    tokens = await login_user(client, test_user)

    response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 204

    session = await get_session(db_session, tokens["refresh_token"])

    await db_session.refresh(session)
    assert session.revoked_at is not None


@pytest.mark.api
async def test_refresh_after_logout(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    logout_response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert logout_response.status_code == 204

    response = await refresh_token_request(client, tokens["refresh_token"])

    assert response.status_code == 401


@pytest.mark.api
async def test_access_token_invalid_after_logout(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    logout_response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert logout_response.status_code == 204

    response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": (f"Bearer {tokens['access_token']}")},
    )

    assert response.status_code == 401


@pytest.mark.api
async def test_logout_is_idempotent(
    client: AsyncClient,
    test_user: User,
) -> None:
    tokens = await login_user(client, test_user)

    for _ in range(2):
        response = await client.post(
            f"{AUTH_URL}/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 204


@pytest.mark.api
async def test_logout_preserves_other_session(
    client: AsyncClient,
    test_user: User,
) -> None:
    first = await login_user(client, test_user)
    second = await login_user(client, test_user)

    response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": first["refresh_token"]},
    )

    assert response.status_code == 204

    first_refresh = await refresh_token_request(client, first["refresh_token"])
    second_refresh = await refresh_token_request(client, second["refresh_token"])

    assert first_refresh.status_code == 401
    assert second_refresh.status_code == 200


@pytest.mark.api
async def test_logout_all_revokes_every_session(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    first = await login_user(client, test_user)
    second = await login_user(client, test_user)

    response = await client.post(
        f"{AUTH_URL}/logout-all",
        headers={"Authorization": (f"Bearer {first['access_token']}")},
    )

    assert response.status_code == 204

    for tokens in (first, second):
        session = await get_session(db_session, tokens["refresh_token"])
        await db_session.refresh(session)
        assert session.revoked_at is not None

        refresh_response = await refresh_token_request(client, tokens["refresh_token"])
        assert refresh_response.status_code == 401

        me_response = await client.get(
            f"{AUTH_URL}/me",
            headers={"Authorization": (f"Bearer {tokens['access_token']}")},
        )
        assert me_response.status_code == 401


@pytest.mark.api
async def test_logout_all_preserves_other_users_sessions(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    # Arrange: User A already exists through the test_user fixture.
    user_a = test_user

    # Create User B using Factory Boy.
    user_b = UserFactory.build()

    db_session.add(user_b)
    await db_session.flush()

    # Create two sessions for User A.
    user_a_session_1 = await login_user(client, user_a)
    user_a_session_2 = await login_user(client, user_a)

    # Create one session for User B.
    user_b_session = await login_user(client, user_b)

    # Act: User A logs out from all devices.
    response = await client.post(
        f"{AUTH_URL}/logout-all",
        headers={"Authorization": (f"Bearer {user_a_session_1['access_token']}")},
    )

    assert response.status_code == 204

    # Assert: Both sessions belonging to User A are revoked.
    for tokens in (user_a_session_1, user_a_session_2):
        session = await get_session(
            db_session,
            tokens["refresh_token"],
        )
        await db_session.refresh(session)

        assert session.revoked_at is not None

        refresh_response = await refresh_token_request(
            client,
            tokens["refresh_token"],
        )
        assert refresh_response.status_code == 401

    # Assert: User B's database session remains active.
    session_b = await get_session(
        db_session,
        user_b_session["refresh_token"],
    )
    await db_session.refresh(session_b)

    assert session_b.revoked_at is None

    # Assert: User B can still refresh their access token.
    refresh_response = await refresh_token_request(
        client,
        user_b_session["refresh_token"],
    )

    assert refresh_response.status_code == 200

    # Assert: User B can still access authenticated endpoints.
    me_response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": (f"Bearer {user_b_session['access_token']}")},
    )

    assert me_response.status_code == 200
    assert me_response.json()["id"] == user_b.id
    assert me_response.json()["email"] == user_b.email
