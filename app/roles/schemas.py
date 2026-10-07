from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleBase(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str = Field(default=None, min_length=3, max_length=50)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if value is None:
            raise ValueError("Role name cannot be null")

        return value.strip()


class RoleResponse(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
