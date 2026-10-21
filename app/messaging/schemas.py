from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, EmailStr, Field, field_validator


class EmailJob(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)

    recipient: EmailStr

    subject: str = Field(
        min_length=1,
        max_length=255,
    )

    text_content: str = Field(min_length=1)

    html_content: str | None = None
    retry_count: int = Field(default=0, ge=0, le=3)
    expires_at: AwareDatetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must be timezone-aware")

        return value


def is_email_job_expired(
    job: EmailJob,
    *,
    now: datetime | None = None,
) -> bool:
    if job.expires_at is None:
        return False

    current_time = now or datetime.now(UTC)

    return job.expires_at <= current_time
