import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import UserRole
from tests.factories.users import UserFactory

pytestmark = pytest.mark.api

USERS_URL = "/api/v1/users"

ROLE_MANAGEMENT_PERMISSIONS = {
    RoleName.ADMIN: {"read", "assign", "update", "delete"},
    RoleName.HR_MANAGER: {"read", "assign", "update", "delete"},
    RoleName.HR_OPERATOR: {"read", "assign", "update", "delete"},
    RoleName.MANAGER: set(),
    RoleName.EMPLOYEE: set(),
}


async def get_role(
    db_session: AsyncSession,
    role_name: RoleName,
) -> Role:
    role = await db_session.scalar(select(Role).where(Role.name == role_name.value))
    assert role is not None
    return role


async def get_role_ids(
    db_session: AsyncSession,
    user_id: int,
) -> set[int]:
    result = await db_session.scalars(
        select(UserRole.role_id).where(UserRole.user_id == user_id)
    )
    return set(result.all())


@pytest.mark.parametrize(
    "actor_role",
    list(RoleName),
    ids=lambda role: role.value,
)
@pytest.mark.parametrize(
    ("operation", "success_status"),
    [
        pytest.param("read", 200, id="read"),
        pytest.param("assign", 201, id="assign"),
        pytest.param("update", 200, id="update"),
        pytest.param("delete", 204, id="delete"),
    ],
)
async def test_user_role_management_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    actor_role: RoleName,
    operation: str,
    success_status: int,
) -> None:
    actor = await create_user_with_role(actor_role)
    headers = await login_as(actor)

    target = UserFactory.build()
    db_session.add(target)
    await db_session.flush()

    employee_role = await get_role(db_session, RoleName.EMPLOYEE)
    manager_role = await get_role(db_session, RoleName.MANAGER)

    if operation in {"update", "delete"}:
        db_session.add(
            UserRole(
                user_id=target.id,
                role_id=employee_role.id,
            )
        )
        await db_session.flush()

    if operation == "read":
        response = await client.get(
            f"{USERS_URL}/{target.id}/roles",
            headers=headers,
        )

    elif operation == "assign":
        response = await client.post(
            f"{USERS_URL}/{target.id}/roles/{manager_role.id}",
            headers=headers,
        )

    elif operation == "update":
        response = await client.put(
            f"{USERS_URL}/{target.id}/roles/",
            json={"role_ids": [manager_role.id]},
            headers=headers,
        )

    elif operation == "delete":
        response = await client.delete(
            f"{USERS_URL}/{target.id}/roles/{employee_role.id}",
            headers=headers,
        )

    else:
        pytest.fail(f"Unsupported operation: {operation}")

    allowed = operation in ROLE_MANAGEMENT_PERMISSIONS[actor_role]
    expected_status = success_status if allowed else 403

    assert response.status_code == expected_status, (
        f"Actor: {actor_role.value}, "
        f"Operation: {operation}, "
        f"Expected: {expected_status}, "
        f"Actual: {response.status_code}, "
        f"Response: {response.text}"
    )

    # Unauthorized requests must not change assignments.
    if not allowed:
        expected_roles = (
            {employee_role.id} if operation in {"update", "delete"} else set()
        )
        assert await get_role_ids(db_session, target.id) == expected_roles


@pytest.mark.parametrize(
    "restricted_role",
    [RoleName.ADMIN, RoleName.HR_MANAGER],
    ids=lambda role: role.value,
)
async def test_hr_operator_cannot_assign_privileged_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    restricted_role: RoleName,
) -> None:
    actor = await create_user_with_role(RoleName.HR_OPERATOR)
    headers = await login_as(actor)

    target = UserFactory.build()
    db_session.add(target)
    await db_session.flush()

    role = await get_role(db_session, restricted_role)

    response = await client.post(
        f"{USERS_URL}/{target.id}/roles/{role.id}",
        headers=headers,
    )

    assert response.status_code == 403, response.text
    assert await get_role_ids(db_session, target.id) == set()


@pytest.mark.parametrize(
    "restricted_role",
    [RoleName.ADMIN, RoleName.HR_MANAGER],
    ids=lambda role: role.value,
)
async def test_hr_operator_cannot_remove_privileged_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    restricted_role: RoleName,
) -> None:
    actor = await create_user_with_role(RoleName.HR_OPERATOR)
    headers = await login_as(actor)

    target = UserFactory.build()
    db_session.add(target)
    await db_session.flush()

    role = await get_role(db_session, restricted_role)

    db_session.add(UserRole(user_id=target.id, role_id=role.id))
    await db_session.flush()

    response = await client.delete(
        f"{USERS_URL}/{target.id}/roles/{role.id}",
        headers=headers,
    )

    assert response.status_code == 403, response.text
    assert await get_role_ids(db_session, target.id) == {role.id}


@pytest.mark.parametrize(
    "restricted_role",
    [RoleName.ADMIN, RoleName.HR_MANAGER],
    ids=lambda role: role.value,
)
async def test_hr_operator_cannot_replace_privileged_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    restricted_role: RoleName,
) -> None:
    actor = await create_user_with_role(RoleName.HR_OPERATOR)
    headers = await login_as(actor)

    target = UserFactory.build()
    db_session.add(target)
    await db_session.flush()

    restricted = await get_role(db_session, restricted_role)
    employee = await get_role(db_session, RoleName.EMPLOYEE)

    db_session.add(
        UserRole(
            user_id=target.id,
            role_id=restricted.id,
        )
    )
    await db_session.flush()

    response = await client.put(
        f"{USERS_URL}/{target.id}/roles/",
        json={"role_ids": [employee.id]},
        headers=headers,
    )

    assert response.status_code == 403, response.text
    assert await get_role_ids(db_session, target.id) == {restricted.id}


@pytest.mark.parametrize(
    "operation",
    ["assign", "update", "delete"],
)
async def test_hr_operator_cannot_modify_own_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    operation: str,
) -> None:
    actor = await create_user_with_role(RoleName.HR_OPERATOR)
    headers = await login_as(actor)

    employee = await get_role(db_session, RoleName.EMPLOYEE)
    operator = await get_role(db_session, RoleName.HR_OPERATOR)

    if operation == "assign":
        response = await client.post(
            f"{USERS_URL}/{actor.id}/roles/{employee.id}",
            headers=headers,
        )

    elif operation == "update":
        response = await client.put(
            f"{USERS_URL}/{actor.id}/roles/",
            json={"role_ids": [employee.id]},
            headers=headers,
        )

    else:
        response = await client.delete(
            f"{USERS_URL}/{actor.id}/roles/{operator.id}",
            headers=headers,
        )

    assert response.status_code == 403, response.text
    assert await get_role_ids(db_session, actor.id) == {operator.id}


@pytest.mark.parametrize(
    "role_name",
    [
        RoleName.EMPLOYEE,
        RoleName.MANAGER,
        RoleName.HR_OPERATOR,
    ],
    ids=lambda role: role.value,
)
async def test_hr_operator_can_assign_allowed_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    role_name: RoleName,
) -> None:
    actor = await create_user_with_role(RoleName.HR_OPERATOR)
    headers = await login_as(actor)

    target = UserFactory.build()
    db_session.add(target)
    await db_session.flush()

    role = await get_role(db_session, role_name)

    response = await client.post(
        f"{USERS_URL}/{target.id}/roles/{role.id}",
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert await get_role_ids(db_session, target.id) == {role.id}
