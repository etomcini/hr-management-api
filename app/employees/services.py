from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.departments.models import Department
from app.email.templates.employee_onboarding_welcome import build_employee_welcome_email
from app.employees.models import Employee, EmployeeNumberCounter
from app.job_titles.models import JobTitle
from app.messaging.outbox import add_email_to_outbox
from app.messaging.schemas import EmailJob
from app.users.models import User

if TYPE_CHECKING:
    from app.employees.schemas import EmployeeCreate, EmployeeUpdate


# -------------------------
# Private helper functions
# -------------------------


async def _generate_employee_number(
    db: AsyncSession,
) -> str:
    counter = await db.get(EmployeeNumberCounter, 1)

    if counter is None:
        counter = EmployeeNumberCounter(
            id=1,
            next_number=1,
        )
        db.add(counter)
        await db.flush()

    number = counter.next_number

    counter.next_number += 1

    return f"EMP-{number:04d}"


async def _validate_user(
    db: AsyncSession,
    user_id: int | None,
    *,
    employee_id: int | None = None,
) -> User | None:
    if user_id is None:
        return None

    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    stmt = select(Employee).where(Employee.user_id == user_id)

    if employee_id is not None:
        stmt = stmt.where(Employee.id != employee_id)

    existing_employee = await db.scalar(stmt)

    if existing_employee is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already assigned to another employee",
        )

    return user


async def _validate_department(
    db: AsyncSession,
    department_id: int | None,
) -> None:
    if department_id is None:
        return

    department = await db.get(
        Department,
        department_id,
    )

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    if not department.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot assign employee to an inactive department",
        )


async def _validate_job_title(
    db: AsyncSession,
    job_title_id: int | None,
) -> None:
    if job_title_id is None:
        return

    job_title = await db.get(
        JobTitle,
        job_title_id,
    )

    if job_title is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job title not found",
        )


async def _validate_manager(
    db: AsyncSession,
    manager_id: int | None,
    *,
    employee_id: int | None = None,
) -> None:
    if manager_id is None:
        return

    if employee_id is not None and manager_id == employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee cannot be their own manager",
        )

    manager = await db.get(
        Employee,
        manager_id,
    )

    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )


async def _get_employee_for_update(
    db: AsyncSession,
    employee_id: int,
) -> Employee:
    stmt = (
        select(Employee)
        .where(Employee.id == employee_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    employee = await db.scalar(stmt)

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    return employee


# -------------------------
# Public service functions
# -------------------------


async def get_db_employees(
    db: AsyncSession, name: str | None = None, skip: int = 0, limit: int = 10
) -> list[Employee]:
    stmt = select(Employee).options(
        selectinload(Employee.user),
        selectinload(Employee.department),
        selectinload(Employee.job_title),
        selectinload(Employee.manager),
    )

    if name:
        search_name = name.strip()

        full_name = Employee.first_name + " " + Employee.last_name

        stmt = stmt.where(full_name.ilike(f"%{search_name}%"))

    stmt = (
        stmt.order_by(
            Employee.first_name,
            Employee.last_name,
        )
        .offset(skip)
        .limit(limit)
    )

    result = await db.scalars(stmt)

    return list(result.all())


async def get_db_employee_by_id(
    db: AsyncSession,
    employee_id: int,
) -> Employee:
    employee = await db.get(
        Employee,
        employee_id,
        options=(
            selectinload(Employee.user),
            selectinload(Employee.department),
            selectinload(Employee.job_title),
            selectinload(Employee.manager),
        ),
    )
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )

    return employee


async def create_db_employee(
    db: AsyncSession,
    employee_data: EmployeeCreate,
) -> Employee:
    user = await _validate_user(
        db,
        employee_data.user_id,
    )

    await _validate_department(
        db,
        employee_data.department_id,
    )

    await _validate_job_title(
        db,
        employee_data.job_title_id,
    )

    await _validate_manager(
        db,
        employee_data.manager_id,
    )

    employee_number = await _generate_employee_number(db)

    employee = Employee(
        **employee_data.model_dump(),
        employee_number=employee_number,
    )

    db.add(employee)

    if user is not None:
        email_content = build_employee_welcome_email()

        job = EmailJob(
            recipient=user.email,
            subject=email_content.subject,
            text_content=email_content.text_content,
            html_content=email_content.html_content,
        )

        add_email_to_outbox(
            db=db,
            job=job,
        )

    await db.commit()
    await db.refresh(employee)

    return employee


async def update_db_employee(
    db: AsyncSession,
    employee_id: int,
    employee_data: EmployeeUpdate,
) -> Employee:
    employee = await _get_employee_for_update(db, employee_id)

    update_data = employee_data.model_dump(exclude_unset=True)

    # Determine whether a new user is being assigned.
    user_id_changed = (
        "user_id" in update_data
        and update_data["user_id"] is not None
        and update_data["user_id"] != employee.user_id
    )

    user: User | None = None

    if "user_id" in update_data:
        user = await _validate_user(
            db,
            update_data["user_id"],
            employee_id=employee.id,
        )

    if "department_id" in update_data:
        await _validate_department(
            db,
            update_data["department_id"],
        )

    if "job_title_id" in update_data:
        await _validate_job_title(
            db,
            update_data["job_title_id"],
        )

    if "manager_id" in update_data:
        await _validate_manager(
            db,
            update_data["manager_id"],
            employee_id=employee.id,
        )

    # Apply validated updates.
    for field, value in update_data.items():
        setattr(employee, field, value)

    # Send welcome email only when user_id changes
    # to a valid, non-null user.
    if user_id_changed and user is not None:
        email_content = build_employee_welcome_email()

        job = EmailJob(
            recipient=user.email,
            subject=email_content.subject,
            text_content=email_content.text_content,
            html_content=email_content.html_content,
        )

        add_email_to_outbox(
            db=db,
            job=job,
        )

    await db.commit()
    await db.refresh(employee)

    return employee


async def delete_db_employee(
    db: AsyncSession,
    employee_id: int,
) -> None:
    employee = await get_db_employee_by_id(db, employee_id)

    await db.delete(employee)
    await db.commit()
