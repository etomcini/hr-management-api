from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.users.models import User

from app.auth.authentication import (
    CurrentUser,
)
from app.auth.schemas import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    MessageResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
)
from app.auth.services import (
    forgot_password,
    logout_all_sessions,
    logout_user,
    refresh_access_token,
    reset_password,
    user_login,
)
from app.dependencies.database import get_db
from app.users.schemas import UserResponse

openapi_tags = [
    {
        "name": "Authentication",
        "description": "Endpoints to manage authentications",
    }
]

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    return await user_login(
        db=db,
        email=form_data.username,
        password=form_data.password,
    )


@router.post(
    "/token/refresh", response_model=AccessTokenResponse, status_code=status.HTTP_200_OK
)
async def refresh_users_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    token_data: RefreshTokenRequest,
) -> AccessTokenResponse:
    return await refresh_access_token(
        db=db,
        refresh_token=token_data.refresh_token,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the currently authenticated user",
)
async def get_me(current_user: CurrentUser) -> User:

    return current_user


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a password reset",
)
async def request_password_reset(
    password_data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await forgot_password(
        db=db,
        email=str(password_data.email),
    )

    return MessageResponse(
        message=(
            "If an account with that email exists, a password reset link has been sent."
        )
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password",
)
async def reset_forgotten_password(
    password_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await reset_password(
        db=db,
        token=password_data.token,
        new_password=password_data.new_password,
    )

    return MessageResponse(
        message="Password has been reset successfully.",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout current session",
)
async def logout(
    token_data: RefreshTokenRequest,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> None:
    await logout_user(
        db=db,
        refresh_token=token_data.refresh_token,
    )


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout from all devices",
)
async def logout_all(
    current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await logout_all_sessions(
        db=db,
        user_id=current_user.id,
    )
