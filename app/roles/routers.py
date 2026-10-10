from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import require_permissions
from app.dependencies.database import get_db
from app.permissions.enums import PermissionName

if TYPE_CHECKING:
    from app.roles import models

from app.roles.schemas import RoleCreate, RoleResponse, RoleUpdate
from app.roles.services import (
    create_db_role,
    delete_db_role,
    get_db_role_by_id,
    get_db_roles,
    update_db_role,
)

openapi_tags = [
    {
        "name": "Roles",
        "description": "Endpoints to manage roles.",
    }
]

router = APIRouter(
    prefix="/api/v1/roles",
    tags=["Roles"],
)


@router.get(
    "/",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.ROLES_READ,
            )
        ),
    ],
    summary="Get all roles or filter by name",
)
async def get_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = None,
) -> list[models.Role]:
    return await get_db_roles(
        db=db,
        name=name,
    )


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.ROLES_READ,
            )
        ),
    ],
    summary="Get a role by ID",
)
async def get_role(
    role_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Role:
    return await get_db_role_by_id(db, role_id)


@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.ROLES_CREATE,
            )
        ),
    ],
)
async def create_role(
    role_data: RoleCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Role:
    return await create_db_role(db, role_data)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.ROLES_UPDATE,
            )
        ),
    ],
    summary="Update role partialy through PATCH",
)
async def update_role(
    role_id: int, role_data: RoleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Role:
    return await update_db_role(db, role_id, role_data)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            require_permissions(
                PermissionName.ROLES_DELETE,
            )
        ),
    ],
)
async def delete_role(
    role_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await delete_db_role(db, role_id)
