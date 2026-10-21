from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.messaging.delivery import ClaimResult, EmailClaim
from app.messaging.schemas import EmailJob
from app.messaging.worker import process_email_job


@pytest.fixture
def email_job() -> EmailJob:
    return EmailJob(
        recipient="test@example.com",
        subject="Test message",
        text_content="Hello from the HR application",
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
async def test_duplicate_delivered_job_is_not_sent(
    monkeypatch: pytest.MonkeyPatch,
    incoming_message: MagicMock,
) -> None:
    claim_mock = AsyncMock(
        return_value=EmailClaim(result=ClaimResult.DELIVERED),
    )
    send_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        claim_mock,
    )
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_mock,
    )

    await process_email_job(incoming_message)

    send_mock.assert_not_awaited()
    incoming_message.ack.assert_awaited_once()
    incoming_message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_failure_does_not_send(
    monkeypatch: pytest.MonkeyPatch,
    incoming_message: MagicMock,
) -> None:
    claim_mock = AsyncMock(
        side_effect=ConnectionError("Database unavailable"),
    )
    send_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        claim_mock,
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


@pytest.mark.asyncio
async def test_successful_delivery_is_recorded_before_ack(
    monkeypatch: pytest.MonkeyPatch,
    incoming_message: MagicMock,
    email_job: EmailJob,
) -> None:
    claim_id = uuid4()
    events: list[str] = []

    async def fake_send_email(**kwargs: object) -> None:
        events.append("smtp")

    async def fake_mark_delivered(
        job_id: object,
        owner_id: object,
    ) -> bool:
        assert job_id == email_job.job_id
        assert owner_id == claim_id
        events.append("database")
        return True

    async def fake_ack() -> None:
        events.append("ack")

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        AsyncMock(
            return_value=EmailClaim(
                result=ClaimResult.CLAIMED,
                claim_id=claim_id,
            )
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        fake_send_email,
    )
    monkeypatch.setattr(
        "app.messaging.worker.mark_email_delivered",
        fake_mark_delivered,
    )

    incoming_message.ack = AsyncMock(side_effect=fake_ack)

    await process_email_job(incoming_message)

    assert events == ["smtp", "database", "ack"]


@pytest.mark.asyncio
async def test_database_failure_after_smtp_does_not_ack(
    monkeypatch: pytest.MonkeyPatch,
    incoming_message: MagicMock,
) -> None:
    claim_id = uuid4()

    send_mock = AsyncMock()
    record_mock = AsyncMock(
        side_effect=ConnectionError("Database unavailable"),
    )

    monkeypatch.setattr(
        "app.messaging.worker.claim_email_job",
        AsyncMock(
            return_value=EmailClaim(
                result=ClaimResult.CLAIMED,
                claim_id=claim_id,
            )
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_mock,
    )
    monkeypatch.setattr(
        "app.messaging.worker.mark_email_delivered",
        record_mock,
    )

    await process_email_job(incoming_message)

    send_mock.assert_awaited_once()
    record_mock.assert_awaited_once()
    incoming_message.ack.assert_not_awaited()
    incoming_message.nack.assert_awaited_once_with(
        requeue=True,
    )
