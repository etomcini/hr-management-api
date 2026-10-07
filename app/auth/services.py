from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, RefreshToken
from app.auth.password_reset import (
    create_password_reset_token,
    hash_password_reset_token,
)
from app.auth.schemas import AccessTokenResponse, Token
from app.core.config import settings
from app.core.datetime import ensure_utc
from app.core.email import send_password_reset_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.users.models import User

# from app.users.services import get_user_by_email


async def user_login(
    db: AsyncSession,
    email: str,
    password: str,
) -> Token:
    # Look up user by email (case sensitive)
    # Note: OAuth2PasswordRequestForm uses "username" field, but we treat it as email
    result = await db.execute(
        select(User).where(
            func.lower(User.email) == email.lower(),
        ),
    )
    user = result.scalars().first()

    # Verify user exists and password is correct
    if user is None or not verify_password(
        password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incoret email or Password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create access token with user id as subject (also create the refresh token)
    access_token_expires = timedelta(minutes=settings.access_token_expire_min)

    refresh_token_expires = timedelta(days=settings.refresh_access_token_expire_days)

    jti = str(uuid4())

    access_token = create_access_token(
        data={"sub": str(user.id)},
        jti=jti,
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        jti=jti,
        expires_delta=refresh_token_expires,
    )

    refresh_session = RefreshToken(
        user_id=user.id, jti=jti, expires_at=datetime.now(UTC) + refresh_token_expires
    )

    db.add(refresh_session)

    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> AccessTokenResponse:
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(refresh_token)

    if payload is None:
        raise invalid_token

    if payload.get("type") != "refresh":
        raise invalid_token

    user_id = payload.get("sub")

    jti = payload.get("jti")

    if jti is None:
        raise invalid_token

    try:
        user_id = int(user_id)
    except TypeError, ValueError:
        raise invalid_token from None

    stmt = select(RefreshToken).where(
        RefreshToken.jti == jti,
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )

    refresh_session = await db.scalar(stmt)

    if refresh_session is None:
        raise invalid_token

    user = await db.get(User, user_id)

    if user is None:
        raise invalid_token

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(data={"sub": str(user.id)}, jti=jti)
    return AccessTokenResponse(access_token=access_token)


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(refresh_token)

    if payload is None:
        raise invalid_token

    if payload.get("type") != "refresh":
        raise invalid_token

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if jti is None:
        raise invalid_token

    try:
        user_id = int(user_id)
    except TypeError, ValueError:
        raise invalid_token from None

    stmt = select(RefreshToken).where(
        RefreshToken.jti == jti,
        RefreshToken.user_id == user_id,
    )

    refresh_session = await db.scalar(stmt)

    if refresh_session is None:
        raise invalid_token

    if refresh_session.revoked_at is None:
        refresh_session.revoked_at = datetime.now(UTC)
        await db.commit()


async def logout_all_sessions(
    db: AsyncSession,
    user_id: int,
) -> None:
    await revoke_all_sessions(
        db=db,
        user_id=user_id,
    )

    await db.commit()


async def revoke_other_sessions(
    db: AsyncSession,
    user_id: int,
    current_jti: str,
) -> None:
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.jti != current_jti,
            RefreshToken.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC),
        )
    )

    await db.execute(stmt)


async def forgot_password(
    db: AsyncSession,
    email: str,
) -> None:
    stmt = select(User).where(
        func.lower(User.email) == email.lower(),
    )

    user = await db.scalar(stmt)

    # Always behave the same way when the account does not exist.
    # This prevents exposing which email addresses are registered.
    if user is None:
        return

    # Do not send password-reset emails for inactive accounts.
    # The API response will still be identical.
    if not user.is_active:
        return

    reset_token = await create_password_reset_token(
        db=db,
        user_id=user.id,
    )

    try:
        await send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token,
        )
    except Exception:
        await db.rollback()
        raise

    await db.commit()


async def revoke_all_sessions(
    db: AsyncSession,
    user_id: int,
) -> None:
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC),
        )
    )

    await db.execute(stmt)


async def reset_password(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    token_hash = hash_password_reset_token(token)

    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash,
    )

    reset_token = await db.scalar(stmt)

    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    now = datetime.now(UTC)

    if reset_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    if ensure_utc(reset_token.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user = await db.get(
        User,
        reset_token.user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    if verify_password(
        new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(new_password)

    reset_token.used_at = now

    await revoke_all_sessions(
        db=db,
        user_id=user.id,
    )

    await db.commit()
