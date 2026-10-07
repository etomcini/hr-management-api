from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

# from sqlalchemy.orm import selectinload
from app.dependencies.database import get_db

if TYPE_CHECKING:
    from app.departments import models

from app.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.departments.services import (
    create_db_department,
    delete_db_department,
    get_db_department_by_id,
    get_db_departments,
    update_db_department,
)

openapi_tags = [
    {"name": "Departments", "description": "Endpoints to manage Departments."}
]

router = APIRouter(
    prefix="/api/v1/departments",
    tags=["Departments"],
)


@router.get(
    "/",
    response_model=list[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all departments or filter by name",
)
async def get_departments(
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = None,
) -> list[models.Department]:
    return await get_db_departments(db, name)


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a department by ID",
)
async def get_department(
    department_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Department:
    return await get_db_department_by_id(db, department_id)


@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    department_data: DepartmentCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Department:
    return await create_db_department(db, department_data)


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update department partialy through PATCH",
)
async def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.Department:
    return await update_db_department(db, department_id, department_data)


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_department(
    department_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await delete_db_department(db, department_id)
