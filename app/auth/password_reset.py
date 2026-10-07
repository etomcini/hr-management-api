import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken
from app.core.config import settings


def generate_password_reset_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = hash_password_reset_token(token)

    return token, token_hash


def hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def invalidate_password_reset_tokens(
    db: AsyncSession,
    user_id: int,
) -> None:
    now = datetime.now(UTC)

    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(
            used_at=now,
        )
    )

    await db.execute(stmt)


async def create_password_reset_token(
    db: AsyncSession,
    user_id: int,
) -> str:
    await invalidate_password_reset_tokens(
        db=db,
        user_id=user_id,
    )

    token, token_hash = generate_password_reset_token()

    reset_token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=(
            datetime.now(UTC)
            + timedelta(
                minutes=settings.password_reset_token_expire_minutes,
            )
        ),
    )

    db.add(reset_token)

    await db.flush()

    return token
