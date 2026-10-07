from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication import CurrentSessionJTI, CurrentUser  # noqa: TC001
from app.auth.authorization import require_permissions
from app.permissions.enums import PermissionName
from app.roles.enums import RoleName
from app.users.models import User

if TYPE_CHECKING:
    from app.roles.models import Role
    from app.users.models import User

from app.dependencies.database import get_db
from app.roles.schemas import RoleResponse
from app.users.schemas import (
    ChangePasswordRequest,
    UserCreate,
    UserResponse,
    UserRoleResponse,
    UserRolesUpdate,
    UserUpdate,
)
from app.users.services import (
    assign_db_role_to_user,
    change_user_password,
    create_db_user,
    delete_db_user,
    get_db_role_users,
    get_db_user_by_id,
    get_db_user_roles,
    get_db_users,
    remove_db_role_from_user,
    update_db_user,
    update_db_user_roles,
)

openapi_tags = [
    {
        "name": "Users / User's Roles",
        "description": "Endpoints to manage users and user's roles",
    }
]

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users / User's Roles"],
)

"""
Routers for users CRUD operations
"""


@router.get(
    "/",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
async def get_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    return await get_db_users(
        db=db,
        email=email,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.USERS_CREATE,
            )
        ),
    ],
)
async def create_user(
    user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    return await create_db_user(db, user_data)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a user by ID",
)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    return await get_db_user_by_id(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a user",
)
async def update_user(
    user_id: int, user_data: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    return await update_db_user(db, user_id, user_data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await delete_db_user(db, user_id)


"""
Endpoints for user-role CRUD operations!
"""


@router.get(
    "/{user_id}/roles",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
    summary="Get roles asigned to a user.",
)
async def get_user_roles(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int
) -> list[Role]:
    return await get_db_user_roles(db, user_id)


@router.get(
    "/{role_id}/users",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get users that heve asigned a specific role.",
)
async def get_role_users(
    db: Annotated[AsyncSession, Depends(get_db)], role_id: int
) -> list[User]:
    return await get_db_role_users(db, role_id)


@router.post(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_user(
    user_id: int, role_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> UserRoleResponse:
    return await assign_db_role_to_user(db, user_id=user_id, role_id=role_id)


@router.put(
    "/{user_id}/roles/",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
    summary="Update user's roles",
)
async def update_user_roles(
    user_id: int,
    role_data: UserRolesUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Role]:
    return await update_db_user_roles(
        db,
        user_id=user_id,
        role_ids=role_data.role_ids,
    )


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user's password",
)
async def change_password(
    password_data: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    current_jti: CurrentSessionJTI,
) -> None:
    await change_user_password(
        db=db,
        user=current_user,
        current_jti=current_jti,
        password_data=password_data,
    )


@router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove user's roles",
)
async def remove_user_roles(
    user_id: int, role_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await remove_db_role_from_user(
        db,
        user_id=user_id,
        role_id=role_id,
    )
