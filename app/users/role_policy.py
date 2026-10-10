from collections.abc import Iterable

from fastapi import HTTPException, status

from app.roles.enums import RoleName
from app.roles.models import Role
from app.users.models import User

HR_OPERATOR_ALLOWED_ROLES = {
    RoleName.EMPLOYEE.value,
    RoleName.MANAGER.value,
    RoleName.HR_OPERATOR.value,
}


def validate_role_changes(
    actor: User,
    roles: Iterable[Role],
    *,
    target_user_id: int,
) -> None:
    actor_roles = {user_role.role.name for user_role in actor.user_roles}

    # Admin and HR Manager can manage assignments.
    if actor_roles.intersection(
        {
            RoleName.ADMIN.value,
            RoleName.HR_MANAGER.value,
        }
    ):
        return

    if RoleName.HR_OPERATOR.value not in actor_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage user roles.",
        )

    # Prevent HR Operators from changing their own roles.
    if actor.id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR Operators cannot modify their own roles.",
        )

    # HR Operators may manage only explicitly approved roles.
    for role in roles:
        if role.name not in HR_OPERATOR_ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "HR Operators may manage only employee, "
                    "manager, and hr_operator roles."
                ),
            )
