from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role

if TYPE_CHECKING:
    from app.roles.schemas import RoleCreate, RoleUpdate


"""
Helper to prevent Admin and HR manager to rename or delete one of five built-in roles.
Since those role names are used by authorization logic and RBAC synchronization, 
this could break the application.
"""

SYSTEM_ROLE_NAMES = {role.value for role in RoleName}


def ensure_role_can_be_renamed_or_deleted(role: Role) -> None:
    if role.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Built-in roles cannot be renamed or deleted."),
        )


async def get_role_by_name(
    db: AsyncSession,
    name: str,
) -> Role | None:
    stmt = select(Role).where(func.lower(Role.name) == name.lower())

    return await db.scalar(stmt)


async def get_db_roles(
    db: AsyncSession,
    name: str | None = None,
) -> list[Role]:
    stmt = select(Role)

    if name is not None:
        stmt = stmt.where(Role.name.ilike(f"%{name.strip()}%"))

    stmt = stmt.order_by(Role.id)

    result = await db.scalars(stmt)

    return list(result.all())


async def get_db_role_by_id(
    db: AsyncSession,
    role_id: int,
) -> Role:
    role = await db.get(Role, role_id)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return role


async def create_db_role(
    db: AsyncSession,
    role_data: RoleCreate,
) -> Role:
    existing_role: Role | None = await get_role_by_name(
        db=db,
        name=role_data.name,
    )

    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This role already exists!",
        )

    role = Role(**role_data.model_dump())

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return role


async def update_db_role(
    db: AsyncSession,
    role_id: int,
    role_data: RoleUpdate,
) -> Role:
    role = await get_db_role_by_id(db=db, role_id=role_id)

    update_data = role_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        new_name = update_data["name"]

        if new_name is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role name cannot be null.",
            )

        if new_name != role.name:
            ensure_role_can_be_renamed_or_deleted(role)

            existing_role = await get_role_by_name(
                db=db,
                name=new_name,
            )

            if existing_role is not None and existing_role.id != role.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Role already exists",
                )

    for field, value in update_data.items():
        setattr(role, field, value)

    await db.commit()
    await db.refresh(role)

    return role


async def delete_db_role(
    db: AsyncSession,
    role_id: int,
) -> None:
    role = await get_db_role_by_id(db=db, role_id=role_id)

    ensure_role_can_be_renamed_or_deleted(role)

    await db.delete(role)
    await db.commit()
