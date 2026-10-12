import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from tests.factories.employees import EmployeeFactory

EMPLOYEE_CRUD_PERMISSIONS = {
    RoleName.ADMIN: {"create", "read", "update", "delete"},
    RoleName.HR_MANAGER: {"create", "read", "update", "delete"},
    RoleName.HR_OPERATOR: {"create", "read", "update"},
    RoleName.MANAGER: {"read"},
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
async def test_employee_crud_permissions(
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

    # Create a separate Employee to update or delete.
    target_employee = None

    if operation in {"update", "delete"}:
        target_employee = EmployeeFactory.build()

        db_session.add(target_employee)
        await db_session.flush()

    # Prepare the correct HTTP request for each operation.
    if operation == "create":
        response = await client.post(
            "/api/v1/employees/",
            json={
                "first_name": "EmployeeFirst",
                "last_name": "EmployeeLast",
                "hire_date": "2026-10-11",
            },
            headers=headers,
        )

    elif operation == "read":
        response = await client.get(
            "/api/v1/employees/",
            headers=headers,
        )

    elif operation == "update":
        assert target_employee is not None
        response = await client.patch(
            f"/api/v1/employees/{target_employee.id}",
            json={
                "first_name": "UpdatedFirst",
                "last_name": "UpdatedLast",
                "hire_date": "2026-10-12",
            },
            headers=headers,
        )

    elif operation == "delete":
        assert target_employee is not None
        response = await client.delete(
            f"/api/v1/employees/{target_employee.id}",
            headers=headers,
        )

    else:
        pytest.fail(f"Unsupported operation: {operation}")

    # Verify authorization.
    allowed = operation in EMPLOYEE_CRUD_PERMISSIONS[role_name]

    expected_status = success_status if allowed else 403

    assert response.status_code == expected_status, (
        f"\nRole: {role_name.value}, "
        f"\nOperation: {operation}, "
        f"\nExpected status: {expected_status}, "
        f"\nActual status: {response.status_code}, "
        f"\nResponse: {response.text}"
    )
