from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DepartmentBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class DepartmentCreate(DepartmentBase):
    manager_id: int | None = None
    parent_department_id: int | None = None


class DepartmentUpdate(BaseModel):
    name: str = Field(default=None, min_length=2, max_length=100)
    code: str = Field(default=None, min_length=2, max_length=20)
    manager_id: int | None = None
    parent_department_id: int | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip()


class DepartmentResponse(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manager_id: int | None
    parent_department_id: int | None
    created_at: datetime
    updated_at: datetime
