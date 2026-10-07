from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


# Create a JWT access token
def create_access_token(
    data: dict, jti: str, expires_delta: timedelta | None = None
) -> str:
    now: datetime = datetime.now(UTC)
    to_encode = data.copy()

    if expires_delta:
        expire = now + expires_delta
    else:
        expire: datetime = now + timedelta(minutes=settings.access_token_expire_min)

    to_encode.update({"jti": jti, "iat": now, "exp": expire, "type": "access"})

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def create_refresh_token(
    data: dict, jti: str, expires_delta: timedelta | None = None
) -> str:
    now: datetime = datetime.now(UTC)
    to_encode = data.copy()
    if expires_delta:
        expire: datetime = now + expires_delta
    else:
        expire: datetime = now + timedelta(
            days=settings.refresh_access_token_expire_days
        )
    to_encode.update({"jti": jti, "iat": now, "exp": expire, "type": "refresh"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


# Verify a JWT access token and return the subject (user ID) if is valid
def verify_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "type", "jti"]},
        )
    except jwt.InvalidTokenError:
        return None

    return payload
