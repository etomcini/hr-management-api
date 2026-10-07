from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import RefreshToken
from app.core.security import oauth2_scheme, verify_token
from app.dependencies.database import get_db
from app.roles.models import Role, RolePermission
from app.users.models import User, UserRole


def get_invalid_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_access_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict[str, Any]:
    payload = verify_token(token)

    if payload is None:
        raise get_invalid_token_exception()

    if payload.get("type") != "access":
        raise get_invalid_token_exception()

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not isinstance(user_id, str):
        raise get_invalid_token_exception()

    try:
        int(user_id)
    except ValueError:
        raise get_invalid_token_exception() from None

    if not isinstance(jti, str) or not jti:
        raise get_invalid_token_exception()

    return payload


AccessTokenPayload = Annotated[
    dict[str, Any],
    Depends(get_access_token_payload),
]


async def get_current_user(
    payload: AccessTokenPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user_id = int(payload["sub"])
    jti = payload["jti"]

    # Verify that the login session still exists, has not been revoked, and has not expired.
    session_stmt = select(RefreshToken.id).where(
        RefreshToken.user_id == user_id,
        RefreshToken.jti == jti,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.now(UTC),
    )

    session_id = await db.scalar(session_stmt)

    if session_id is None:
        raise get_invalid_token_exception()

    # Load the authenticated user and their roles.
    user_stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
    )

    user = await db.scalar(user_stmt)

    if user is None:
        raise get_invalid_token_exception()

    # A valid session does not override an inactive account.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


async def get_current_session_jti(
    payload: AccessTokenPayload,
) -> str:
    return payload["jti"]


CurrentSessionJTI = Annotated[
    str,
    Depends(get_current_session_jti),
]
