import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User, UserRole
from tests.factories.users import UserFactory

pytestmark = pytest.mark.api

USERS_URL = "/api/v1/users"


async def get_role(db_session: AsyncSession, name: RoleName) -> Role:
    role = await db_session.scalar(select(Role).where(Role.name == name.value))
    assert role is not None
    return role


async def get_assigned_role_ids(db_session: AsyncSession, user_id: int) -> set[int]:
    result = await db_session.scalars(
        select(UserRole.role_id).where(UserRole.user_id == user_id)
    )
    return set(result.all())


@pytest.fixture
async def admin_headers(create_user_with_role, login_as):
    admin = await create_user_with_role(RoleName.ADMIN)
    return await login_as(admin)


@pytest.fixture
async def target_user(db_session: AsyncSession) -> User:
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()
    return user


async def test_assign_role_to_user(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    role = await get_role(db_session, RoleName.MANAGER)

    response = await client.post(
        f"{USERS_URL}/{target_user.id}/roles/{role.id}",
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json() == {
        "user_id": target_user.id,
        "role_id": role.id,
    }
    assert role.id in await get_assigned_role_ids(db_session, target_user.id)


async def test_assign_duplicate_role_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    role = await get_role(db_session, RoleName.MANAGER)
    db_session.add(UserRole(user_id=target_user.id, role_id=role.id))
    await db_session.flush()

    response = await client.post(
        f"{USERS_URL}/{target_user.id}/roles/{role.id}",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Role already assigned to user"


@pytest.mark.parametrize(
    ("missing", "expected_detail"),
    [
        ("user", "User not found"),
        ("role", "Role not found"),
    ],
)
async def test_assign_role_missing_record(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
    missing: str,
    expected_detail: str,
) -> None:
    role = await get_role(db_session, RoleName.MANAGER)

    user_id = -1 if missing == "user" else target_user.id
    role_id = -1 if missing == "role" else role.id

    response = await client.post(
        f"{USERS_URL}/{user_id}/roles/{role_id}",
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == expected_detail


async def test_get_user_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    manager = await get_role(db_session, RoleName.MANAGER)
    employee = await get_role(db_session, RoleName.EMPLOYEE)

    db_session.add_all(
        [
            UserRole(user_id=target_user.id, role_id=manager.id),
            UserRole(user_id=target_user.id, role_id=employee.id),
        ]
    )
    await db_session.flush()

    response = await client.get(
        f"{USERS_URL}/{target_user.id}/roles",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert {role["id"] for role in response.json()} == {
        manager.id,
        employee.id,
    }


async def test_get_roles_for_missing_user(client: AsyncClient, admin_headers) -> None:
    response = await client.get(
        f"{USERS_URL}/-1/roles",
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


async def test_get_users_assigned_to_role(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    manager = await get_role(db_session, RoleName.MANAGER)

    db_session.add(UserRole(user_id=target_user.id, role_id=manager.id))
    await db_session.flush()

    response = await client.get(
        f"{USERS_URL}/{manager.id}/users",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert target_user.id in {user["id"] for user in response.json()}


async def test_get_users_for_missing_role(client: AsyncClient, admin_headers) -> None:
    response = await client.get(
        f"{USERS_URL}/-1/users",
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


async def test_replace_user_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    employee = await get_role(db_session, RoleName.EMPLOYEE)
    manager = await get_role(db_session, RoleName.MANAGER)
    hr_operator = await get_role(db_session, RoleName.HR_OPERATOR)

    db_session.add_all(
        [
            UserRole(user_id=target_user.id, role_id=employee.id),
            UserRole(user_id=target_user.id, role_id=manager.id),
        ]
    )
    await db_session.flush()

    response = await client.put(
        f"{USERS_URL}/{target_user.id}/roles/",
        json={"role_ids": [manager.id, hr_operator.id]},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert {role["id"] for role in response.json()} == {
        manager.id,
        hr_operator.id,
    }
    assert await get_assigned_role_ids(db_session, target_user.id) == {
        manager.id,
        hr_operator.id,
    }


async def test_replace_roles_with_missing_role_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    employee = await get_role(db_session, RoleName.EMPLOYEE)
    db_session.add(UserRole(user_id=target_user.id, role_id=employee.id))
    await db_session.flush()

    response = await client.put(
        f"{USERS_URL}/{target_user.id}/roles/",
        json={"role_ids": [-1]},
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text
    assert await get_assigned_role_ids(db_session, target_user.id) == {employee.id}


async def test_replace_roles_with_empty_list_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    employee = await get_role(db_session, RoleName.EMPLOYEE)
    db_session.add(UserRole(user_id=target_user.id, role_id=employee.id))
    await db_session.flush()

    response = await client.put(
        f"{USERS_URL}/{target_user.id}/roles/",
        json={"role_ids": []},
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    assert await get_assigned_role_ids(db_session, target_user.id) == {employee.id}


async def test_remove_role_from_user(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    employee = await get_role(db_session, RoleName.EMPLOYEE)
    manager = await get_role(db_session, RoleName.MANAGER)

    db_session.add_all(
        [
            UserRole(user_id=target_user.id, role_id=employee.id),
            UserRole(user_id=target_user.id, role_id=manager.id),
        ]
    )
    await db_session.flush()

    response = await client.delete(
        f"{USERS_URL}/{target_user.id}/roles/{manager.id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text
    assert await get_assigned_role_ids(db_session, target_user.id) == {employee.id}


async def test_remove_unassigned_role_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    target_user: User,
) -> None:
    manager = await get_role(db_session, RoleName.MANAGER)

    response = await client.delete(
        f"{USERS_URL}/{target_user.id}/roles/{manager.id}",
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Role is not assigned to user"
