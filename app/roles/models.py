from __future__ import (
    annotations,  # In Python 3.10 and later, this import is not necessary, but it is still useful for forward references in type hints.
)

from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dependencies.database import Base
from app.roles.enums import RoleName

if TYPE_CHECKING:
    from app.permissions.models import Permission
    from app.users.models import UserRole


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        default=RoleName.EMPLOYEE.value,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )

    permission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped[Role] = relationship(
        back_populates="role_permissions",
    )

    permission: Mapped[Permission] = relationship(
        back_populates="role_permissions",
    )
