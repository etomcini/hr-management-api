from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.permissions.enums import PermissionName
from app.permissions.models import Permission
from app.roles.enums import RoleName
from app.roles.models import Role, RolePermission

PERMISSIONS = {
    PermissionName.USERS_READ: "Read users",
    PermissionName.USERS_CREATE: "Create users",
    PermissionName.USERS_UPDATE: "Update users",
    PermissionName.USERS_DELETE: "Delete users",
    PermissionName.EMPLOYEES_READ: "Read employees",
    PermissionName.EMPLOYEES_CREATE: "Create employees",
    PermissionName.EMPLOYEES_UPDATE: "Update employees",
    PermissionName.EMPLOYEES_DELETE: "Delete employees",
    PermissionName.ROLES_READ: "Read roles",
    PermissionName.ROLES_CREATE: "Create roles",
    PermissionName.ROLES_UPDATE: "Update roles",
    PermissionName.ROLES_DELETE: "Delete roles",
    PermissionName.ROLES_ASSIGN: "Assign roles to users",
}


ROLE_PERMISSIONS = {
    RoleName.ADMIN: {
        PermissionName.USERS_READ,
        PermissionName.USERS_CREATE,
        PermissionName.USERS_UPDATE,
        PermissionName.USERS_DELETE,
        PermissionName.EMPLOYEES_READ,
        PermissionName.EMPLOYEES_CREATE,
        PermissionName.EMPLOYEES_UPDATE,
        PermissionName.EMPLOYEES_DELETE,
        PermissionName.ROLES_READ,
        PermissionName.ROLES_CREATE,
        PermissionName.ROLES_UPDATE,
        PermissionName.ROLES_DELETE,
        PermissionName.ROLES_ASSIGN,
    },
    RoleName.HR_MANAGER: {
        PermissionName.USERS_READ,
        PermissionName.USERS_CREATE,
        PermissionName.USERS_UPDATE,
        PermissionName.EMPLOYEES_READ,
        PermissionName.EMPLOYEES_CREATE,
        PermissionName.EMPLOYEES_UPDATE,
        PermissionName.EMPLOYEES_DELETE,
        PermissionName.ROLES_READ,
        PermissionName.ROLES_ASSIGN,
    },
    RoleName.HR_OPERATOR: {
        PermissionName.USERS_READ,
        PermissionName.USERS_CREATE,
        PermissionName.USERS_UPDATE,
        PermissionName.EMPLOYEES_READ,
        PermissionName.EMPLOYEES_CREATE,
        PermissionName.EMPLOYEES_UPDATE,
    },
    RoleName.MANAGER: {
        PermissionName.EMPLOYEES_READ,
    },
    RoleName.EMPLOYEE: set(),
}


async def seed_permissions(db: AsyncSession) -> None:
    result = await db.execute(select(Permission))

    existing_permissions = {permission.name for permission in result.scalars().all()}

    for permission_name, description in PERMISSIONS.items():
        if permission_name.value not in existing_permissions:
            db.add(
                Permission(
                    name=permission_name.value,
                    description=description,
                )
            )

    await db.commit()


async def seed_role_permissions(db: AsyncSession) -> None:
    roles_result = await db.execute(select(Role))
    roles = {role.name: role for role in roles_result.scalars().all()}

    permissions_result = await db.execute(select(Permission))
    permissions = {
        permission.name: permission for permission in permissions_result.scalars().all()
    }

    existing_result = await db.execute(select(RolePermission))

    existing_assignments = {
        (
            role_permission.role_id,
            role_permission.permission_id,
        )
        for role_permission in existing_result.scalars().all()
    }

    for role_name, permission_names in ROLE_PERMISSIONS.items():
        role = roles.get(role_name.value)

        if role is None:
            continue

        for permission_name in permission_names:
            permission = permissions.get(permission_name.value)

            if permission is None:
                continue

            assignment = (
                role.id,
                permission.id,
            )

            if assignment not in existing_assignments:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )

    await db.commit()


async def seed_rbac(db: AsyncSession) -> None:
    await seed_permissions(db)
    await seed_role_permissions(db)
