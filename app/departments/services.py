from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.departments.models import Department

if TYPE_CHECKING:
    from app.departments.schemas import DepartmentCreate, DepartmentUpdate


# A helper function to prevent non duplicating department names
async def get_department_by_name(
    db: AsyncSession,
    name: str,
) -> Department | None:
    stmt = select(Department).where(func.lower(Department.name) == name.lower())

    return await db.scalar(stmt)


async def get_department_by_code(
    db: AsyncSession,
    code: str,
) -> Department | None:
    stmt = select(Department).where(func.lower(Department.code) == code.lower())
    return await db.scalar(stmt)


async def get_db_departments(
    db: AsyncSession,
    name: str | None = None,
) -> list[Department]:
    stmt = select(Department)

    if name is not None:
        stmt = stmt.where(Department.name.ilike(f"%{name.strip()}%"))

    stmt = stmt.order_by(Department.id)

    result = await db.scalars(stmt)

    return list(result(all))


async def get_db_department_by_id(
    db: AsyncSession,
    department_id: int,
) -> Department:
    department = await db.get(Department, department_id)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    return department


async def create_db_department(
    db: AsyncSession,
    department_data: DepartmentCreate,
) -> Department:
    existing_department: Department | None = await get_department_by_name(
        db=db,
        name=department_data.name,
    )

    if existing_department:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This department already exists.",
        )

    existing_department_code = await get_department_by_code(
        db=db,
        code=department_data.code,
    )

    if existing_department_code is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This department code already exists.",
        )

    department = Department(**department_data.model_dump())

    db.add(department)
    await db.commit()
    await db.refresh(department)

    return department


async def update_db_department(
    db: AsyncSession,
    department_id: int,
    department_data: DepartmentUpdate,
) -> Department:
    department = await get_db_department_by_id(
        db=db,
        department_id=department_id,
    )

    update_data = department_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        name = update_data["name"].strip()

        existing_department = await get_department_by_name(
            db=db,
            name=name,
        )

        if existing_department is not None and existing_department.id != department.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A department with this name already exists.",
            )

        update_data["name"] = name

    if "code" in update_data:
        code = update_data["code"]

        existing_department_code = await get_department_by_code(
            db=db,
            code=code,
        )

        if (
            existing_department_code is not None
            and existing_department_code.id != department.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A department with this code already exists.",
            )

    for field, value in update_data.items():
        setattr(department, field, value)

    await db.commit()
    await db.refresh(department)

    return department


async def delete_db_department(
    db: AsyncSession,
    department_id: int,
) -> None:
    department = await get_db_department_by_id(
        db=db,
        department_id=department_id,
    )

    await db.delete(department)
    await db.commit()
