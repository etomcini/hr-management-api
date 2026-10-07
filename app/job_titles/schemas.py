from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobTitleBase(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class JobTitleCreate(JobTitleBase):
    pass


class JobTitleUpdate(BaseModel):
    name: str = Field(default=None, min_length=3, max_length=50)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class JobTitleResponse(JobTitleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
