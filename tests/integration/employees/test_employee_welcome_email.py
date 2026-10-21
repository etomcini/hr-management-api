from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.employees.models import Employee
from app.employees.schemas import EmployeeCreate, EmployeeUpdate
from app.employees.services import (
    create_db_employee,
    update_db_employee,
)
from app.messaging.models import OutboxMessage
from app.messaging.schemas import EmailJob
from app.users.models import User
from tests.factories.employees import EmployeeFactory


async def get_outbox_messages(
    db: AsyncSession,
) -> list[OutboxMessage]:
    result = await db.scalars(
        select(OutboxMessage).where(
            OutboxMessage.event_type == "email.send",
        )
    )
    return list(result.all())


async def test_create_employee_with_user_creates_welcome_email(
    db_session: AsyncSession,
    test_user: User,
):
    employee_data = EmployeeCreate(
        first_name="John",
        last_name="Smith",
        hire_date=EmployeeFactory.build().hire_date,
        user_id=test_user.id,
    )

    employee = await create_db_employee(
        db=db_session,
        employee_data=employee_data,
    )

    assert employee.id is not None
    assert employee.user_id == test_user.id

    messages = await get_outbox_messages(db_session)

    assert len(messages) == 1

    job = EmailJob.model_validate(messages[0].payload)

    assert job.recipient == test_user.email
    assert job.expires_at is None
    assert "welcome" in job.subject.lower()


async def test_create_employee_without_user_creates_no_email(
    db_session: AsyncSession,
):
    employee_data = EmployeeCreate(
        first_name="Jane",
        last_name="Smith",
        hire_date=EmployeeFactory.build().hire_date,
        user_id=None,
    )

    employee = await create_db_employee(
        db=db_session,
        employee_data=employee_data,
    )

    assert employee.id is not None
    assert employee.user_id is None

    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_assign_user_to_employee_creates_welcome_email(
    db_session: AsyncSession,
    test_employee,
    test_user: User,
):
    assert test_employee.user_id is None

    updated_employee = await update_db_employee(
        db=db_session,
        employee_id=test_employee.id,
        employee_data=EmployeeUpdate(
            user_id=test_user.id,
        ),
    )

    assert updated_employee.user_id == test_user.id

    messages = await get_outbox_messages(db_session)

    assert len(messages) == 1

    job = EmailJob.model_validate(messages[0].payload)

    assert job.recipient == test_user.email


async def test_same_user_assignment_does_not_create_email(
    db_session: AsyncSession,
    test_employee,
    test_user: User,
):
    test_employee.user_id = test_user.id
    await db_session.flush()

    await update_db_employee(
        db=db_session,
        employee_id=test_employee.id,
        employee_data=EmployeeUpdate(
            user_id=test_user.id,
        ),
    )

    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_update_employee_name_does_not_create_email(
    db_session: AsyncSession,
    test_employee,
):
    employee = await update_db_employee(
        db=db_session,
        employee_id=test_employee.id,
        employee_data=EmployeeUpdate(
            first_name="UpdatedName",
        ),
    )

    assert employee.first_name == "UpdatedName"

    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_remove_user_assignment_does_not_create_email(
    db_session: AsyncSession,
    test_employee,
    test_user: User,
):
    test_employee.user_id = test_user.id
    await db_session.flush()

    employee = await update_db_employee(
        db=db_session,
        employee_id=test_employee.id,
        employee_data=EmployeeUpdate(
            user_id=None,
        ),
    )

    assert employee.user_id is None

    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_outbox_failure_rolls_back_employee_update(
    db_session: AsyncSession,
    test_employee: Employee,
    test_user: User,
):
    employee_id = test_employee.id
    user_id = test_user.id

    # Preserve fixture records in the outer test transaction.
    await db_session.commit()

    assert test_employee.user_id is None

    with (
        patch(
            "app.employees.services.add_email_to_outbox",
            side_effect=IntegrityError(
                statement="INSERT INTO email_outbox",
                params={},
                orig=Exception("Simulated outbox failure"),
            ),
        ),
        pytest.raises(IntegrityError),
    ):
        await update_db_employee(
            db=db_session,
            employee_id=employee_id,
            employee_data=EmployeeUpdate(
                user_id=user_id,
            ),
        )

    await db_session.rollback()

    employee = await db_session.get(
        Employee,
        employee_id,
        populate_existing=True,
    )

    assert employee is not None
    assert employee.user_id is None

    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_outbox_failure_rolls_back_employee_creation(
    db_session: AsyncSession,
    test_user: User,
):
    employee_data = EmployeeCreate(
        first_name="RollbackTest",
        last_name="Employee",
        hire_date=date.today(),  # noqa: DTZ011
        user_id=test_user.id,
    )

    # Count existing employees before the operation.
    employee_ids_before = set((await db_session.scalars(select(Employee.id))).all())

    # Simulate failure while adding the welcome email
    # to the transactional outbox.
    with (
        patch(
            "app.employees.services.add_email_to_outbox",
            side_effect=IntegrityError(
                statement="INSERT INTO email_outbox",
                params={},
                orig=Exception("Simulated outbox failure"),
            ),
        ),
        pytest.raises(IntegrityError),
    ):
        await create_db_employee(
            db=db_session,
            employee_data=employee_data,
        )

    # The service failed before committing.
    # Roll back the uncommitted employee creation.
    await db_session.rollback()

    db_session.expire_all()

    employee_ids_after = set((await db_session.scalars(select(Employee.id))).all())

    assert employee_ids_after == employee_ids_before

    # No welcome email should have been persisted.
    messages = await get_outbox_messages(db_session)

    assert messages == []


async def test_real_outbox_insert_failure_rolls_back_employee_creation(
    db_session: AsyncSession,
    test_user: User,
):
    user_id = test_user.id

    # Preserve fixture user in the outer transaction.
    await db_session.commit()

    employee_data = EmployeeCreate(
        first_name="Atomicity",
        last_name="TestEmployee",
        hire_date=date.today(),  # noqa: DTZ011
        user_id=user_id,
    )

    stmt = select(Employee).where(
        Employee.first_name == "Atomicity",
        Employee.last_name == "TestEmployee",
        Employee.user_id == user_id,
    )

    assert await db_session.scalar(stmt) is None

    # This assumes event_type is NOT NULL in PostgreSQL.
    invalid_outbox = OutboxMessage(
        event_type=None,
        payload={},
    )

    db_session.add(invalid_outbox)

    with pytest.raises(IntegrityError):
        await create_db_employee(
            db=db_session,
            employee_data=employee_data,
        )

    await db_session.rollback()

    # Verify employee creation was rolled back.
    assert await db_session.scalar(stmt) is None
