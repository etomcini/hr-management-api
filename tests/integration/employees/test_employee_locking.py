import asyncio

import pytest
from sqlalchemy import delete, select

from app.dependencies.database import AsyncSessionLocal
from app.employees.models import Employee
from app.employees.schemas import EmployeeUpdate
from app.employees.services import update_db_employee
from app.messaging.models import OutboxMessage
from app.messaging.schemas import EmailJob
from app.users.models import User
from tests.factories.employees import EmployeeFactory
from tests.factories.users import UserFactory


@pytest.mark.asyncio
async def test_employee_row_lock_serializes_updates():
    # Create an employee committed to PostgreSQL.
    async with AsyncSessionLocal.begin() as db:
        employee = EmployeeFactory.build()
        db.add(employee)
        await db.flush()
        employee_id = employee.id

    try:
        async with AsyncSessionLocal() as session_a, AsyncSessionLocal() as session_b:
            stmt = select(Employee).where(Employee.id == employee_id).with_for_update()

            locked_a = await session_a.scalar(stmt)

            assert locked_a is not None

            # Modify the row while holding the lock.
            locked_a.first_name = "UpdatedByA"
            await session_a.flush()

            task_b = asyncio.create_task(session_b.scalar(stmt))

            # Session B should remain blocked.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task_b),
                    timeout=0.2,
                )

            # Commit releases the lock.
            await session_a.commit()

            locked_b = await asyncio.wait_for(
                task_b,
                timeout=5,
            )

            assert locked_b is not None
            assert locked_b.first_name == "UpdatedByA"

            await session_b.rollback()

    finally:
        async with AsyncSessionLocal.begin() as db:
            employee = await db.get(Employee, employee_id)

            if employee is not None:
                await db.delete(employee)


@pytest.mark.asyncio
async def test_concurrent_same_user_assignment_creates_one_email():
    # Arrange: create committed records visible to
    # independent PostgreSQL sessions.
    async with AsyncSessionLocal.begin() as db:
        user = UserFactory.build()
        employee = EmployeeFactory.build()

        db.add_all([user, employee])
        await db.flush()

        user_id = user.id
        user_email = user.email
        employee_id = employee.id

    try:

        async def assign_user() -> None:
            async with AsyncSessionLocal() as db:
                await update_db_employee(
                    db=db,
                    employee_id=employee_id,
                    employee_data=EmployeeUpdate(
                        user_id=user_id,
                    ),
                )

        # Act: both calls use separate sessions.
        await asyncio.gather(
            assign_user(),
            assign_user(),
        )

        # Assert: inspect committed PostgreSQL state.
        async with AsyncSessionLocal() as db:
            updated_employee = await db.get(
                Employee,
                employee_id,
            )

            assert updated_employee is not None
            assert updated_employee.user_id == user_id

            result = await db.scalars(
                select(OutboxMessage).where(
                    OutboxMessage.event_type == "email.send",
                )
            )

            messages = list(result.all())

            # Filter by the test user's email to avoid
            # counting unrelated messages.
            matching_jobs = [
                EmailJob.model_validate(message.payload)
                for message in messages
                if message.payload.get("recipient") == user_email
            ]

            assert len(matching_jobs) == 1
            assert matching_jobs[0].recipient == user_email
            assert matching_jobs[0].expires_at is None

    finally:
        # Clean up committed test records.
        async with AsyncSessionLocal.begin() as db:
            await db.execute(
                delete(OutboxMessage).where(
                    OutboxMessage.event_type == "email.send",
                    OutboxMessage.payload["recipient"].astext == user_email,
                )
            )

            employee = await db.get(Employee, employee_id)
            if employee is not None:
                await db.delete(employee)

            user = await db.get(User, user_id)
            if user is not None:
                await db.delete(user)
