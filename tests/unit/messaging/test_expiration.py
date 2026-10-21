from datetime import UTC, datetime, timedelta

import pytest

from app.messaging.schemas import EmailJob, is_email_job_expired


@pytest.fixture
def email_job() -> EmailJob:
    return EmailJob(
        recipient="test@example.com",
        subject="Test",
        text_content="Test message",
    )


def test_email_without_expiration_is_not_expired(
    email_job: EmailJob,
) -> None:
    assert is_email_job_expired(email_job) is False


def test_email_with_future_expiration_is_not_expired(
    email_job: EmailJob,
) -> None:
    now = datetime.now(UTC)

    job = email_job.model_copy(
        update={"expires_at": now + timedelta(minutes=30)},
    )

    assert is_email_job_expired(job, now=now) is False


def test_email_with_past_expiration_is_expired(
    email_job: EmailJob,
) -> None:
    now = datetime.now(UTC)

    job = email_job.model_copy(
        update={"expires_at": now - timedelta(seconds=1)},
    )

    assert is_email_job_expired(job, now=now) is True


def test_email_expiring_at_current_time_is_expired(
    email_job: EmailJob,
) -> None:
    now = datetime.now(UTC)

    job = email_job.model_copy(
        update={"expires_at": now},
    )

    assert is_email_job_expired(job, now=now) is True


def test_naive_expiration_is_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EmailJob(
            recipient="test@example.com",
            subject="Test",
            text_content="Test message",
            expires_at=datetime(2026, 10, 19),  # noqa: DTZ001
        )
