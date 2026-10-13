# from collections.abc import Callable
# from typing import TYPE_CHECKING

# from fastapi import HTTPException, status

# from app.auth.authentication import CurrentUser

# if TYPE_CHECKING:
#     from app.users.models import User


# def require_roles(*allowed_roles: str) -> Callable:
#     def check_roles(current_user: CurrentUser) -> User:
#         user_roles = {user_role.role.name for user_role in current_user.user_roles}

#         if not user_roles.intersection(allowed_roles):
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="You do not have permission to perform this action.",
#             )

#         return current_user

#     return check_roles

from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.auth.authentication import CurrentUser

if TYPE_CHECKING:
    from app.permissions.enums import PermissionName
    from app.roles.enums import RoleName
    from app.users.models import User


def require_roles(
    *allowed_roles: RoleName,
) -> Callable[[CurrentUser], User]:

    def check_roles(current_user: CurrentUser) -> User:
        user_roles = {user_role.role.name for user_role in current_user.user_roles}

        allowed_role_names = {role.value for role in allowed_roles}

        if user_roles.isdisjoint(allowed_role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Role doesn't permit to perform this action.",
            )

        return current_user

    return check_roles


def require_permissions(
    *required_permissions: PermissionName,
) -> Callable[[CurrentUser], User]:

    def check_permissions(current_user: CurrentUser) -> User:
        user_permissions = {
            role_permission.permission.name
            for user_role in current_user.user_roles
            for role_permission in user_role.role.role_permissions
        }

        required = {permission.value for permission in required_permissions}

        if not required.issubset(user_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return check_permissions
