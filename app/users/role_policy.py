from collections.abc import Iterable

from fastapi import HTTPException, status

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User

PROTECTED_ROLES = {
    RoleName.ADMIN,
    RoleName.HR_MANAGER,
}


def validate_role_changes(
    actor: User,
    roles: Iterable[Role],
) -> None:
    actor_roles = {user_role.role.name for user_role in actor.user_roles}

    # Admin and HR Manager can manage all role assignments.
    if actor_roles.intersection(
        {
            RoleName.ADMIN.value,
            RoleName.HR_MANAGER.value,
        }
    ):
        return

    # HR Operator may only manage unprotected roles.
    if RoleName.HR_OPERATOR.value not in actor_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage user roles.",
        )

    for role in roles:
        if role.name in {protected_role.value for protected_role in PROTECTED_ROLES}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "HR Operators cannot assign, update, "
                    "or remove Admin or HR Manager roles."
                ),
            )
