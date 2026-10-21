from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
)

from app.core.config import Environment, settings
from app.dependencies.database import engine, get_db
from app.employees.models import Employee
from app.main import app
from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User, UserRole
from tests.factories.employees import EmployeeFactory
from tests.factories.users import UserFactory


@pytest.fixture(scope="session", autouse=True)
def verify_test_environment() -> None:
    if settings.app_env != Environment.TESTING:
        pytest.fail(
            "Tests require APP_ENV=testing.",
            pytrace=False,
        )

    url = make_url(settings.database_url)

    if (
        url.database != "hr_test_db"
        or url.username != "test_user"
        or url.host != "test-db"
    ):
        pytest.fail(
            "Tests require the dedicated Docker test database.",
            pytrace=False,
        )


@pytest.fixture
async def db_connection() -> AsyncGenerator[AsyncConnection]:
    """Create an isolated outer transaction for each test."""
    async with engine.connect() as connection:
        transaction = await connection.begin()

        try:
            yield connection
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture
async def db_session(
    db_connection: AsyncConnection,
) -> AsyncGenerator[AsyncSession]:
    """Create a session that uses SAVEPOINTs."""
    session_factory = async_sessionmaker(
        bind=db_connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with session_factory() as session:
        yield session


@pytest.fixture
async def test_user(
    db_session: AsyncSession,
) -> User:
    user = UserFactory.build()

    db_session.add(user)

    await db_session.flush()

    return user


@pytest.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """Create an HTTP client using the isolated DB session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def create_user_with_role(
    db_session: AsyncSession,
):
    async def create(role_name: RoleName) -> User:
        role = await db_session.scalar(select(Role).where(Role.name == role_name.value))

        assert role is not None, f"Required test role {role_name.value!r} is missing"

        user = UserFactory.build()

        db_session.add(user)
        await db_session.flush()

        db_session.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
            )
        )
        await db_session.flush()

        return user

    return create


@pytest.fixture
def login_as(client: AsyncClient):
    async def login(user: User) -> dict[str, str]:
        response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": user.email,
                "password": "TestPassword123!",
            },
        )

        assert response.status_code == 200, response.text

        access_token = response.json()["access_token"]

        return {
            "Authorization": f"Bearer {access_token}",
        }

    return login


@pytest.fixture
async def test_employee(
    db_session: AsyncSession,
) -> Employee:
    employee = EmployeeFactory.build()

    db_session.add(employee)
    await db_session.flush()

    return employee
