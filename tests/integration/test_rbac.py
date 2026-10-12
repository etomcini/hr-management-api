import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.permissions.models import Permission
from app.roles.enums import RoleName
from app.roles.models import Role
from app.seeds.permissions import PERMISSIONS, seed_rbac


@pytest.mark.integration
async def test_all_predefined_roles_exist(
    db_session: AsyncSession,
) -> None:
    result = await db_session.scalars(select(Role.name))

    existing_roles = set(result.all())

    expected_roles = {role.value for role in RoleName}

    assert expected_roles.issubset(existing_roles)


@pytest.mark.integration
async def test_all_predefined_permissions_exist(
    db_session: AsyncSession,
) -> None:
    result = await db_session.scalars(select(Permission.name))

    existing_permissions = set(result.all())

    expected_permissions = {permission.value for permission in PERMISSIONS}

    assert expected_permissions.issubset(existing_permissions)


@pytest.mark.integration
async def test_rbac_seeding_is_idempotent(
    db_session: AsyncSession,
) -> None:
    await seed_rbac(db_session)
    await seed_rbac(db_session)

    roles_result = await db_session.scalars(select(Role.name))
    permission_result = await db_session.scalars(select(Permission.name))

    roles = roles_result.all()
    permissions = permission_result.all()

    assert len(roles) == len(set(roles))
    assert len(permissions) == len(set(permissions))
