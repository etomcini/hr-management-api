from __future__ import (
    annotations,  # In Python 3.10 and later, this import is not necessary, but it is still useful for forward references in type hints.
)

from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dependencies.database import Base

if TYPE_CHECKING:
    from app.employees.models import Employee


class JobTitle(Base):
    __tablename__ = "job_titles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    employees: Mapped[list[Employee]] = relationship(back_populates="job_title")
