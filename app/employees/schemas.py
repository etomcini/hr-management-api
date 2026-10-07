from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.employees.enums import EmploymentStatus


class EmployeeBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(
        min_length=2,
        max_length=100,
    )

    last_name: str = Field(
        min_length=2,
        max_length=100,
    )

    hire_date: date

    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE


class EmployeeCreate(EmployeeBase):
    user_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    job_title_id: int | None = Field(default=None, gt=0)
    manager_id: int | None = Field(default=None, gt=0)


class EmployeeUpdate(BaseModel):
    user_id: int | None = Field(default=None, gt=0)

    first_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    last_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    department_id: int | None = Field(default=None, gt=0)
    job_title_id: int | None = Field(default=None, gt=0)
    manager_id: int | None = Field(default=None, gt=0)
    hire_date: date | None = None
    employment_status: EmploymentStatus | None = None


class EmployeeResponse(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_number: str
    user_id: int | None
    department_id: int | None
    job_title_id: int | None
    manager_id: int | None
    created_at: datetime
    updated_at: datetime
