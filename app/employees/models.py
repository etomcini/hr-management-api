from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dependencies.database import Base
from app.employees.enums import EmploymentStatus

if TYPE_CHECKING:
    from app.departments.models import Department
    from app.job_titles.models import JobTitle
    from app.users.models import User


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=True,
    )

    employee_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    job_title_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_titles.id"),
        nullable=True,
        index=True,
    )

    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
        index=True,
    )

    hire_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    employment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmploymentStatus.ACTIVE.value,
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

    # Relationships

    user: Mapped[User | None] = relationship(
        "User",
        back_populates="employee",
    )

    department: Mapped[Department | None] = relationship(
        "Department",
        foreign_keys=lambda: [Employee.department_id],
        back_populates="employees",
    )

    job_title: Mapped[JobTitle | None] = relationship(
        back_populates="employees",
    )

    manager: Mapped[Employee | None] = relationship(
        "Employee",
        remote_side=lambda: [Employee.id],
        back_populates="direct_reports",
    )

    direct_reports: Mapped[list[Employee]] = relationship(
        "Employee",
        back_populates="manager",
    )

    managed_departments: Mapped[list[Department]] = relationship(
        "Department",
        foreign_keys="Department.manager_id",
        back_populates="manager",
    )


class EmployeeNumberCounter(Base):
    __tablename__ = "employee_number_counters"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    next_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
