from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dependencies.database import Base

if TYPE_CHECKING:
    from app.employees.models import Employee


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "employees.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_departments_manager_id_employees",
        ),
        nullable=True,
    )

    parent_department_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "departments.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Department manager
    manager: Mapped[Employee | None] = relationship(
        "Employee",
        foreign_keys=lambda: [Department.manager_id],
        back_populates="managed_departments",
    )

    # Parent department
    parent_department: Mapped[Department | None] = relationship(
        "Department",
        remote_side=lambda: [Department.id],
        foreign_keys=[parent_department_id],
        back_populates="child_departments",
    )

    # Child departments
    child_departments: Mapped[list[Department]] = relationship(
        "Department",
        back_populates="parent_department",
        foreign_keys=[parent_department_id],
    )

    employees: Mapped[list[Employee]] = relationship(
        "Employee",
        foreign_keys="Employee.department_id",
        back_populates="department",
    )
