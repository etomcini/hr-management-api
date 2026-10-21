from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.messaging.delivery import ClaimResult, EmailClaim
from app.messaging.schemas import EmailJob
from app.messaging.worker import process_email_job


@pytest.fixture
def email_job() -> EmailJob:
    return EmailJob(
        recipient="test@example.com",
        subject="Test BUSY job",
        text_content="Test message",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )


@pytest.fixture
def incoming_message(email_job: EmailJob) -> MagicMock:
    message = MagicMock()
    message.body = email_job.model_dump_json().encode()
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    message.reject = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_busy_job_is_deferred_and_acknowledged(
    monkeypatch: pytest.MonkeyPatch,
    email_job: EmailJob,
    incoming_message: MagicMock,
) -> None:
    publish_mock = AsyncMock()
    send_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        AsyncMock(
            return_value=EmailClaim(
                result=ClaimResult.BUSY,
            )
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_busy",
        publish_mock,
    )
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_mock,
    )

    await process_email_job(incoming_message)

    publish_mock.assert_awaited_once_with(email_job)
    send_mock.assert_not_awaited()
    incoming_message.ack.assert_awaited_once()
    incoming_message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_busy_publish_failure_requeues_original(
    monkeypatch: pytest.MonkeyPatch,
    incoming_message: MagicMock,
) -> None:
    send_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        AsyncMock(
            return_value=EmailClaim(
                result=ClaimResult.BUSY,
            )
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_busy",
        AsyncMock(
            side_effect=ConnectionError("RabbitMQ unavailable"),
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_mock,
    )

    await process_email_job(incoming_message)

    send_mock.assert_not_awaited()
    incoming_message.ack.assert_not_awaited()
    incoming_message.nack.assert_awaited_once_with(
        requeue=True,
    )
