import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User, UserRole

pytestmark = pytest.mark.api

USERS_URL = "/api/v1/users"

ADMIN_SAFETY_ERROR = "Operation denied: at least one active Admin must remain."


async def get_role(
    db_session: AsyncSession,
    role_name: RoleName,
) -> Role:
    role = await db_session.scalar(select(Role).where(Role.name == role_name.value))
    assert role is not None
    return role


async def get_user_role_ids(
    db_session: AsyncSession,
    user_id: int,
) -> set[int]:
    result = await db_session.scalars(
        select(UserRole.role_id).where(UserRole.user_id == user_id)
    )
    return set(result.all())


@pytest.fixture
async def sole_admin(
    create_user_with_role,
    login_as,
):
    admin = await create_user_with_role(RoleName.ADMIN)
    headers = await login_as(admin)
    return admin, headers


async def test_cannot_delete_last_active_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    sole_admin,
) -> None:
    admin, headers = sole_admin

    response = await client.delete(
        f"{USERS_URL}/{admin.id}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ADMIN_SAFETY_ERROR

    # The user must still exist.
    user = await db_session.get(User, admin.id)
    assert user is not None
    assert user.is_active is True


async def test_cannot_deactivate_last_active_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    sole_admin,
) -> None:
    admin, headers = sole_admin

    response = await client.patch(
        f"{USERS_URL}/{admin.id}",
        json={"is_active": False},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ADMIN_SAFETY_ERROR

    await db_session.refresh(admin)
    assert admin.is_active is True


async def test_cannot_remove_last_admin_role(
    client: AsyncClient,
    db_session: AsyncSession,
    sole_admin,
) -> None:
    admin, headers = sole_admin
    admin_role = await get_role(db_session, RoleName.ADMIN)

    response = await client.delete(
        f"{USERS_URL}/{admin.id}/roles/{admin_role.id}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ADMIN_SAFETY_ERROR

    assert admin_role.id in await get_user_role_ids(db_session, admin.id)


async def test_cannot_replace_last_admin_role(
    client: AsyncClient,
    db_session: AsyncSession,
    sole_admin,
) -> None:
    admin, headers = sole_admin

    admin_role = await get_role(db_session, RoleName.ADMIN)
    employee_role = await get_role(db_session, RoleName.EMPLOYEE)

    response = await client.put(
        f"{USERS_URL}/{admin.id}/roles/",
        json={"role_ids": [employee_role.id]},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ADMIN_SAFETY_ERROR

    assert await get_user_role_ids(db_session, admin.id) == {admin_role.id}


@pytest.mark.parametrize(
    "operation",
    ["delete", "deactivate", "remove_role", "replace_roles"],
)
async def test_admin_changes_allowed_when_another_active_admin_exists(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    operation: str,
) -> None:
    # Two active Admin users.
    actor = await create_user_with_role(RoleName.ADMIN)
    target = await create_user_with_role(RoleName.ADMIN)

    headers = await login_as(actor)

    admin_role = await get_role(db_session, RoleName.ADMIN)
    employee_role = await get_role(db_session, RoleName.EMPLOYEE)

    if operation == "delete":
        response = await client.delete(
            f"{USERS_URL}/{target.id}",
            headers=headers,
        )
        expected_status = 204

    elif operation == "deactivate":
        response = await client.patch(
            f"{USERS_URL}/{target.id}",
            json={"is_active": False},
            headers=headers,
        )
        expected_status = 200

    elif operation == "remove_role":
        response = await client.delete(
            f"{USERS_URL}/{target.id}/roles/{admin_role.id}",
            headers=headers,
        )
        expected_status = 204

    elif operation == "replace_roles":
        response = await client.put(
            f"{USERS_URL}/{target.id}/roles/",
            json={"role_ids": [employee_role.id]},
            headers=headers,
        )
        expected_status = 200

    else:
        pytest.fail(f"Unsupported operation: {operation}")

    assert response.status_code == expected_status, response.text

    if operation == "delete":
        assert await db_session.get(User, target.id) is None

    elif operation == "deactivate":
        await db_session.refresh(target)
        assert target.is_active is False

    elif operation == "remove_role":
        assert admin_role.id not in await get_user_role_ids(db_session, target.id)

    elif operation == "replace_roles":
        assert await get_user_role_ids(db_session, target.id) == {employee_role.id}

    # The remaining Admin must still be active and retain the Admin role.
    await db_session.refresh(actor)
    assert actor.is_active is True
    assert admin_role.id in await get_user_role_ids(db_session, actor.id)


async def test_inactive_admin_does_not_count_as_backup(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
) -> None:
    active_admin = await create_user_with_role(RoleName.ADMIN)
    inactive_admin = await create_user_with_role(RoleName.ADMIN)

    inactive_admin.is_active = False
    await db_session.flush()

    headers = await login_as(active_admin)
    admin_role = await get_role(db_session, RoleName.ADMIN)

    response = await client.delete(
        f"{USERS_URL}/{active_admin.id}/roles/{admin_role.id}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ADMIN_SAFETY_ERROR

    assert admin_role.id in await get_user_role_ids(db_session, active_admin.id)
