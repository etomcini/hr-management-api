from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.enums import RoleName
from app.roles.models import Role


async def seed_roles(db: AsyncSession) -> None:
    existing_roles = await db.scalars(select(Role.name))
    existing_names = set(existing_roles.all())

    for role_name in RoleName:
        if role_name.value not in existing_names:
            db.add(
                Role(
                    name=role_name.value,
                )
            )

    await db.flush()
