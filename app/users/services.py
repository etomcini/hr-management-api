from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.services import revoke_other_sessions
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.roles.models import Role
from app.roles.services import get_role_by_name
from app.users.admin_safety import (
    ensure_another_active_admin,
    lock_admin_role,
)
from app.users.models import User, UserRole
from app.users.role_policy import validate_role_changes

if TYPE_CHECKING:
    from app.users.schemas import ChangePasswordRequest, UserCreate, UserUpdate

# -------------------------------------
# DB services for users CRUD operations
# -------------------------------------


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.lower())

    return await db.scalar(stmt)


async def get_db_users(
    db: AsyncSession,
    email: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[User]:
    stmt = select(User)

    if email is not None:
        stmt = stmt.where(User.email.ilike(f"%{email.strip()}%"))

    stmt = stmt.order_by(User.id).offset(skip).limit(limit)

    result = await db.scalars(stmt)

    return list(result.all())


async def get_db_user_by_id(
    db: AsyncSession,
    user_id: int,
) -> User:
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


async def create_db_user(
    db: AsyncSession,
    user_data: UserCreate,
) -> User:
    existing_user: User | None = await get_user_by_email(
        db=db,
        email=user_data.email,
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists!",
        )

    # Get the default "emplyee" role
    default_user_role: Role = await get_role_by_name(db=db, name=settings.default_role)

    if default_user_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default employee role is not configured.",
        )

    user = User(
        **user_data.model_dump(exclude={"password"}),
        password_hash=hash_password(user_data.password),
    )

    db.add(user)
    # Generate user.id lwithout commiting yet
    await db.flush()

    # Assign the dofault role "employee" to user
    user_role = UserRole(user_id=user.id, role_id=default_user_role.id)

    db.add(user_role)

    # Finally commit user + role assignment together
    await db.commit()
    await db.refresh(user)

    return user


async def update_db_user(
    db: AsyncSession,
    user_id: int,
    user_data: UserUpdate,
) -> User:
    admin_role = await lock_admin_role(db)
    user = await lock_user_for_role_change(db, user_id)

    update_data = user_data.model_dump(exclude_unset=True)

    if "email" in update_data:
        email = update_data["email"].strip()

        if email.lower() != user.email.lower():
            existing_user = await get_user_by_email(
                db=db,
                email=email,
            )

            if existing_user is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )

        update_data["email"] = email

    if user.is_active and update_data.get("is_active") is False:
        admin_assignment = await db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == admin_role.id,
            )
        )

        if admin_assignment is not None:
            await ensure_another_active_admin(
                db,
                excluded_user_id=user_id,
                admin_role_id=admin_role.id,
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return user


async def change_user_password(
    db: AsyncSession,
    user: User,
    current_jti: str,
    password_data: ChangePasswordRequest,
) -> None:
    if not verify_password(
        password_data.current_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if verify_password(
        password_data.new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(password_data.new_password)

    await revoke_other_sessions(
        db=db,
        user_id=user.id,
        current_jti=current_jti,
    )

    await db.commit()


async def delete_db_user(
    db: AsyncSession,
    user_id: int,
) -> None:
    admin_role = await lock_admin_role(db)
    user = await lock_user_for_role_change(db, user_id)

    if user.is_active:
        admin_assignment = await db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == admin_role.id,
            )
        )

        if admin_assignment is not None:
            await ensure_another_active_admin(
                db,
                excluded_user_id=user_id,
                admin_role_id=admin_role.id,
            )

    await db.delete(user)
    await db.commit()


# -----------------------------------------
# DB services for user-role CRUD operations
# -----------------------------------------


# Helper to prevent concurrent requests from overwriting each other's work
async def lock_user_for_role_change(
    db: AsyncSession,
    user_id: int,
) -> User:
    stmt = select(User).where(User.id == user_id).with_for_update()

    user = await db.scalar(stmt)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


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


async def ensure_role_not_assigned(
    db: AsyncSession,
    user_id: int,
    role_id: int,
) -> None:
    stmt = select(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
    )

    existing_user_role = await db.scalar(stmt)

    if existing_user_role is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already assigned to user",
        )


async def get_db_user_roles(
    db: AsyncSession,
    user_id: int,
) -> list[Role]:
    await get_db_user_by_id(
        db=db,
        user_id=user_id,
    )

    stmt = (
        select(Role)
        .join(UserRole)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )

    result = await db.scalars(stmt)

    return list(result.all())


async def get_db_role_users(
    db: AsyncSession,
    role_id: int,
) -> list[User]:
    await get_db_role_by_id(
        db=db,
        role_id=role_id,
    )

    stmt = (
        select(User).join(UserRole).where(UserRole.role_id == role_id).order_by(User.id)
    )

    result = await db.scalars(stmt)

    return list(result.all())


async def assign_db_role_to_user(
    db: AsyncSession,
    user_id: int,
    role_id: int,
    actor: User,
) -> UserRole:
    await lock_admin_role(db)
    await lock_user_for_role_change(db, user_id)

    role = await get_db_role_by_id(db, role_id)

    validate_role_changes(
        actor=actor,
        roles=[role],
        target_user_id=user_id,
    )

    await ensure_role_not_assigned(
        db=db,
        user_id=user_id,
        role_id=role_id,
    )

    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
    )

    db.add(user_role)

    await db.commit()
    await db.refresh(user_role)

    return user_role


async def update_db_user_roles(
    db: AsyncSession,
    user_id: int,
    role_ids: list[int],
    actor: User,
) -> list[Role]:
    admin_role = await lock_admin_role(db)
    user = await lock_user_for_role_change(db, user_id)

    requested_role_ids = set(role_ids)

    roles_result = await db.scalars(select(Role).where(Role.id.in_(requested_role_ids)))

    roles = list(roles_result.all())

    found_role_ids = {role.id for role in roles}
    missing_role_ids = requested_role_ids - found_role_ids

    if missing_role_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Roles not found: {sorted(missing_role_ids)}",
        )

    user_roles_result = await db.scalars(
        select(UserRole).where(UserRole.user_id == user_id)
    )

    current_user_roles = list(user_roles_result.all())

    current_role_ids = {user_role.role_id for user_role in current_user_roles}

    # Calculate the difference.
    role_ids_to_add = requested_role_ids - current_role_ids
    role_ids_to_remove = current_role_ids - requested_role_ids

    # Validate every role that will change.
    changed_role_ids = role_ids_to_add | role_ids_to_remove

    if changed_role_ids:
        changed_roles_result = await db.scalars(
            select(Role).where(Role.id.in_(changed_role_ids))
        )

        validate_role_changes(
            actor=actor,
            roles=list(changed_roles_result.all()),
            target_user_id=user_id,
        )

    if user.is_active and admin_role.id in role_ids_to_remove:
        await ensure_another_active_admin(
            db,
            excluded_user_id=user_id,
            admin_role_id=admin_role.id,
        )

    # Remove roles.
    for user_role in current_user_roles:
        if user_role.role_id in role_ids_to_remove:
            await db.delete(user_role)

    # Add roles.
    for role_id in role_ids_to_add:
        db.add(
            UserRole(
                user_id=user_id,
                role_id=role_id,
            )
        )

    await db.commit()

    return sorted(roles, key=lambda role: role.name)


async def remove_db_role_from_user(
    db: AsyncSession,
    user_id: int,
    role_id: int,
    actor: User,
) -> None:
    # Always acquire the shared lock first.
    admin_role = await lock_admin_role(db)

    # Then acquire the target-user lock.
    user = await lock_user_for_role_change(db, user_id)

    role = await get_db_role_by_id(db, role_id)

    validate_role_changes(
        actor=actor,
        roles=[role],
        target_user_id=user_id,
    )

    stmt = select(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
    )

    user_role = await db.scalar(stmt)

    if user_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role is not assigned to user",
        )

    if role.id == admin_role.id and user.is_active:
        await ensure_another_active_admin(
            db,
            excluded_user_id=user_id,
            admin_role_id=admin_role.id,
        )

    await db.delete(user_role)
    await db.commit()
