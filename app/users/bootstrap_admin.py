from __future__ import annotations

import asyncio
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401
from app.core.security import hash_password
from app.dependencies.database import AsyncSessionLocal, engine
from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User, UserRole


async def bootstrap_admin(db: AsyncSession) -> None:
    # Serialize bootstrap attempts using the system Admin role.
    admin_role = await db.scalar(
        select(Role).where(Role.name == RoleName.ADMIN.value).with_for_update()
    )

    if admin_role is None:
        raise RuntimeError(
            "Admin role does not exist. Initialize system roles before bootstrapping."
        )

    user_count = await db.scalar(select(func.count(User.id)))

    # Never create another bootstrap account on an existing DB.
    if user_count != 0:
        active_admin_count = await db.scalar(
            select(func.count(User.id))
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                UserRole.role_id == admin_role.id,
                User.is_active.is_(True),
            )
        )

        if not active_admin_count:
            raise RuntimeError(
                "Users exist, but no active Admin was found. "
                "Manual administrator recovery is required."
            )

        print("Bootstrap skipped: database already initialized.")
        return

    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")

    if not email or not password:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_EMAIL and "
            "BOOTSTRAP_ADMIN_PASSWORD are required "
            "for initial setup."
        )

    if len(password) < 12:
        raise RuntimeError(
            "Bootstrap Admin password must contain at least 12 characters."
        )

    user = User(
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )

    db.add(user)
    await db.flush()

    db.add(
        UserRole(
            user_id=user.id,
            role_id=admin_role.id,
        )
    )

    print("Initial Admin account created successfully.")


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db, db.begin():
            await bootstrap_admin(db)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
