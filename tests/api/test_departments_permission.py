import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from tests.factories.departments import DepartmentFactory

DEPARTMENT_CRUD_PERMISSIONS = {
    RoleName.ADMIN: {"create", "read", "update", "delete"},
    RoleName.HR_MANAGER: {"create", "read", "update", "delete"},
    RoleName.HR_OPERATOR: {"create", "read", "update", "delete"},
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
async def test_department_crud_permissions(
    client: AsyncClient,
    create_user_with_role,
    db_session: AsyncSession,
    login_as,
    role_name: RoleName,
    success_status: int,
    operation: str,
) -> None:
    # Create the authenticated user.
    actor = await create_user_with_role(role_name)
    headers = await login_as(actor)

    # Create a separate department to update or delete.
    target_department = None

    if operation in {"update", "delete"}:
        target_department = DepartmentFactory.build()

        db_session.add(target_department)
        await db_session.flush()

    # Execute CRUD operation.
    if operation == "create":
        response = await client.post(
            "/api/v1/departments/",
            json={
                "name": "new_test_department",
                "code": "NCD",
            },
            headers=headers,
        )

    elif operation == "read":
        response = await client.get(
            "/api/v1/departments/",
            headers=headers,
        )

    elif operation == "update":
        assert target_department is not None

        response = await client.patch(
            f"/api/v1/departments/{target_department.id}",
            json={
                "name": "updated_test_department",
                "code": "UCD",
            },
            headers=headers,
        )

    elif operation == "delete":
        assert target_department is not None

        response = await client.delete(
            f"/api/v1/departments/{target_department.id}",
            headers=headers,
        )

    else:
        pytest.fail(f"Unsupported operation: {operation}")

    # Verify permissions
    allowed = operation in DEPARTMENT_CRUD_PERMISSIONS[role_name]

    expected_status = success_status if allowed else 403

    assert response.status_code == expected_status, (
        f"\nRole: {role_name.value}, "
        f"\nOperation: {operation}, "
        f"\nExpected status: {expected_status}, "
        f"\nActual status: {response.status_code}, "
        f"\nResponse: {response.text}"
    )
