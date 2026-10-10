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
    PermissionName.USER_ROLES_READ: "View user's assigned roles",
    PermissionName.USER_ROLES_ASSIGN: "Assign roles to users",
    PermissionName.USER_ROLES_UPDATE: "Update user's assigned roles",
    PermissionName.USER_ROLES_DELETE: "Remove roles from users",
    PermissionName.JOB_POSITIONS_READ: "Read job positions",
    PermissionName.JOB_POSITIONS_CREATE: "Create job positions",
    PermissionName.JOB_POSITIONS_UPDATE: "Update job positions",
    PermissionName.JOB_POSITIONS_DELETE: "Remove job positions",
    PermissionName.DEPARTMENTS_READ: "Read departments",
    PermissionName.DEPARTMENTS_CREATE: "Create departments",
    PermissionName.DEPARTMENTS_UPDATE: "Update departments",
    PermissionName.DEPARTMENTS_DELETE: "Remove departments",
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
        PermissionName.USER_ROLES_READ,
        PermissionName.USER_ROLES_ASSIGN,
        PermissionName.USER_ROLES_UPDATE,
        PermissionName.USER_ROLES_DELETE,
        PermissionName.JOB_POSITIONS_READ,
        PermissionName.JOB_POSITIONS_UPDATE,
        PermissionName.JOB_POSITIONS_CREATE,
        PermissionName.JOB_POSITIONS_DELETE,
        PermissionName.DEPARTMENTS_READ,
        PermissionName.DEPARTMENTS_UPDATE,
        PermissionName.DEPARTMENTS_CREATE,
        PermissionName.DEPARTMENTS_DELETE,
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
        PermissionName.USER_ROLES_READ,
        PermissionName.USER_ROLES_ASSIGN,
        PermissionName.USER_ROLES_UPDATE,
        PermissionName.USER_ROLES_DELETE,
        PermissionName.JOB_POSITIONS_READ,
        PermissionName.JOB_POSITIONS_UPDATE,
        PermissionName.JOB_POSITIONS_CREATE,
        PermissionName.JOB_POSITIONS_DELETE,
        PermissionName.DEPARTMENTS_READ,
        PermissionName.DEPARTMENTS_UPDATE,
        PermissionName.DEPARTMENTS_CREATE,
        PermissionName.DEPARTMENTS_DELETE,
    },
    RoleName.HR_OPERATOR: {
        PermissionName.USERS_READ,
        PermissionName.USERS_CREATE,
        PermissionName.USERS_UPDATE,
        PermissionName.EMPLOYEES_READ,
        PermissionName.EMPLOYEES_CREATE,
        PermissionName.EMPLOYEES_UPDATE,
        PermissionName.ROLES_READ,
        PermissionName.USER_ROLES_READ,
        PermissionName.USER_ROLES_ASSIGN,
        PermissionName.USER_ROLES_UPDATE,
        PermissionName.USER_ROLES_DELETE,
        PermissionName.JOB_POSITIONS_READ,
        PermissionName.JOB_POSITIONS_UPDATE,
        PermissionName.JOB_POSITIONS_CREATE,
        PermissionName.JOB_POSITIONS_DELETE,
        PermissionName.DEPARTMENTS_READ,
        PermissionName.DEPARTMENTS_UPDATE,
        PermissionName.DEPARTMENTS_CREATE,
        PermissionName.DEPARTMENTS_DELETE,
    },
    RoleName.MANAGER: {
        PermissionName.EMPLOYEES_READ,
    },
    RoleName.EMPLOYEE: set(),
}


async def seed_permissions(db: AsyncSession) -> None:
    result = await db.scalars(select(Permission))

    existing = {permission.name: permission for permission in result.all()}

    for permission_name, description in PERMISSIONS.items():
        name = permission_name.value

        permission = existing.get(name)

        if permission is None:
            db.add(
                Permission(
                    name=name,
                    description=description,
                )
            )
        elif permission.description != description:
            permission.description = description

    await db.flush()


async def seed_role_permissions(db: AsyncSession) -> None:
    roles_result = await db.scalars(select(Role))
    roles = {role.name: role for role in roles_result.all()}

    permissions_result = await db.scalars(select(Permission))
    permissions = {
        permission.name: permission for permission in permissions_result.all()
    }

    existing_result = await db.scalars(select(RolePermission))

    existing_assignments = {
        (rp.role_id, rp.permission_id): rp for rp in existing_result.all()
    }

    for role_name, permission_names in ROLE_PERMISSIONS.items():
        role = roles.get(role_name.value)

        if role is None:
            raise RuntimeError(f"Required role '{role_name.value}' is missing")

        desired_permission_ids = {
            permissions[name.value].id for name in permission_names
        }

        # Add missing associations.
        for permission_id in desired_permission_ids:
            key = (role.id, permission_id)

            if key not in existing_assignments:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission_id,
                    )
                )

        # Remove associations no longer configured.
        for (role_id, permission_id), assignment in existing_assignments.items():
            if role_id == role.id and permission_id not in desired_permission_ids:
                await db.delete(assignment)

    await db.flush()


async def seed_rbac(db: AsyncSession) -> None:
    await seed_permissions(db)
    await seed_role_permissions(db)
