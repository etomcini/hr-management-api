import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from tests.factories.users import UserFactory

USER_CRUD_PERMISSIONS = {
    RoleName.ADMIN: {"create", "read", "update", "delete"},
    RoleName.HR_MANAGER: {"create", "read", "update"},
    RoleName.HR_OPERATOR: {"create", "read", "update"},
    RoleName.MANAGER: set(),
    RoleName.EMPLOYEE: set(),
}


@pytest.mark.api
@pytest.mark.parametrize(
    ("operation", "success_status"),
    [
        pytest.param("create", 201, id="create"),
        pytest.param("read", 200, id="read"),
        pytest.param("update", 200, id="update"),
        pytest.param("delete", 204, id="delete"),
    ],
)
@pytest.mark.parametrize(
    "role_name",
    list(RoleName),
    ids=lambda role: role.value,
)
async def test_user_crud_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user_with_role,
    login_as,
    role_name: RoleName,
    operation: str,
    success_status: int,
) -> None:
    # Create the user who will perform the operation.
    actor = await create_user_with_role(role_name)
    headers = await login_as(actor)

    # Create a separate user to update or delete.
    target_user = UserFactory.build()
    db_session.add(target_user)
    await db_session.flush()

    # Prepare the correct HTTP request for each operation.
    if operation == "create":
        response = await client.post(
            "/api/v1/users/",
            json={
                "email": "newuser@example.com",
                "password": "TestPassword123!",
            },
            headers=headers,
        )

    elif operation == "read":
        response = await client.get(
            "/api/v1/users/",
            headers=headers,
        )

    elif operation == "update":
        response = await client.patch(
            f"/api/v1/users/{target_user.id}",
            json={"email": "updated@example.com"},
            headers=headers,
        )

    elif operation == "delete":
        response = await client.delete(
            f"/api/v1/users/{target_user.id}",
            headers=headers,
        )

    else:
        pytest.fail(f"Unsupported operation: {operation}")

    allowed = operation in USER_CRUD_PERMISSIONS[role_name]
    expected_status = success_status if allowed else 403

    assert response.status_code == expected_status, (
        f"\nRole: {role_name.value}, "
        f"\nOperation: {operation}, "
        f"\nExpected status: {expected_status}, "
        f"\nActual status: {response.status_code}, "
        f"\nResponse: {response.text}"
    )
