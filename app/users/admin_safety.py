from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User, UserRole


async def lock_admin_role(db: AsyncSession) -> Role:
    stmt = select(Role).where(Role.name == RoleName.ADMIN.value).with_for_update()

    role = await db.scalar(stmt)

    if role is None:
        raise RuntimeError("System Admin role is missing")

    return role


async def ensure_another_active_admin(
    db: AsyncSession,
    *,
    excluded_user_id: int,
    admin_role_id: int,
) -> None:
    stmt = (
        select(func.count(User.id))
        .join(UserRole, UserRole.user_id == User.id)
        .where(
            UserRole.role_id == admin_role_id,
            User.is_active.is_(True),
            User.id != excluded_user_id,
        )
    )

    remaining_admins = await db.scalar(stmt)

    if not remaining_admins:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Operation denied: at least one active Admin must remain."),
        )
