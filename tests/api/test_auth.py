import pytest
from httpx import AsyncClient

from app.users.models import User


@pytest.mark.api
async def test_login_success(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)
    assert data["access_token"]
    assert data["refresh_token"]


@pytest.mark.api
async def test_login_wrong_password(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


@pytest.mark.api
async def test_login_nonexistent_user(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": "missing@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 401


@pytest.mark.api
async def test_login_inactive_user(
    client: AsyncClient,
    test_user: User,
    db_session,
) -> None:
    test_user.is_active = False

    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


@pytest.mark.api
async def test_get_me_with_valid_token(
    client: AsyncClient,
    test_user: User,
) -> None:
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": "TestPassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == test_user.id
    assert response.json()["email"] == test_user.email


@pytest.mark.api
async def test_get_me_without_token(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/auth/me",
    )

    assert response.status_code == 401


@pytest.mark.api
async def test_get_me_with_invalid_token(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401
