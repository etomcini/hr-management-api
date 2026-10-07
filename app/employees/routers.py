from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import require_permissions
from app.dependencies.database import get_db
from app.permissions.enums import PermissionName

if TYPE_CHECKING:
    from app.employees import models

from app.employees.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.employees.services import (
    create_db_employee,
    delete_db_employee,
    get_db_employee_by_id,
    get_db_employees,
    update_db_employee,
)

openapi_tags = [{"name": "Employees", "description": "Endpoints to manage employees."}]

router = APIRouter(
    prefix="/api/v1/employees",
    tags=["Employees"],
)


@router.get(
    "/",
    response_model=list[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get employees",
    description="Return all employees or filter employees by name.",
)
async def get_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = None,
    skip: int = 0,
    limit: int = 10,
) -> list[models.Employee]:
    return await get_db_employees(db=db, name=name, skip=skip, limit=limit)


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an employee by ID",
)
async def get_employee(
    employee_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Employee:

    return await get_db_employee_by_id(db, employee_id)


@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.EMPLOYEES_CREATE,
            )
        ),
    ],
)
async def create_employee(
    employee_data: EmployeeCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Employee:
    return await create_db_employee(db, employee_data)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update an employee",
)
async def update_employee(
    employee_id: int,
    employee_data: EmployeeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.Employee:
    return await update_db_employee(
        db=db,
        employee_id=employee_id,
        employee_data=employee_data,
    )


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.EMPLOYEES_DELETE,
            )
        ),
    ],
)
async def delete_employee(
    employee_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await delete_db_employee(
        db=db,
        employee_id=employee_id,
    )
