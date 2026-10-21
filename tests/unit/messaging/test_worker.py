from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.messaging.schemas import EmailJob
from app.messaging.worker import process_email_job


@pytest.fixture
def email_job() -> EmailJob:
    return EmailJob(
        job_id=uuid4(),
        type="email.send",
        recipient="test@example.com",
        subject="Test email",
        text_content="Hello from the HR application!",
        html_content=None,
    )


@pytest.fixture
def rabbitmq_message(email_job: EmailJob) -> MagicMock:
    message = MagicMock()

    message.body = email_job.model_dump_json().encode("utf-8")
    message.message_id = str(email_job.job_id)

    message.ack = AsyncMock()
    message.reject = AsyncMock()
    message.nack = AsyncMock()

    return message


@pytest.mark.asyncio
async def test_email_delivery_success(
    monkeypatch: pytest.MonkeyPatch,
    email_job: EmailJob,
    rabbitmq_message: MagicMock,
) -> None:
    send_email_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_email_mock,
    )

    await process_email_job(rabbitmq_message)

    send_email_mock.assert_awaited_once_with(
        to_email=email_job.recipient,
        subject=email_job.subject,
        text_content=email_job.text_content,
        html_content=email_job.html_content,
    )

    rabbitmq_message.ack.assert_awaited_once()
    rabbitmq_message.reject.assert_not_awaited()
    rabbitmq_message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_temporary_failure_publishes_retry(
    monkeypatch: pytest.MonkeyPatch,
    rabbitmq_message: MagicMock,
) -> None:
    send_email_mock = AsyncMock(
        side_effect=TimeoutError("SMTP timeout"),
    )
    publish_retry_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_email_mock,
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        publish_retry_mock,
    )

    await process_email_job(rabbitmq_message)

    publish_retry_mock.assert_awaited_once()

    retry_job = publish_retry_mock.await_args.args[0]

    assert retry_job.retry_count == 1

    rabbitmq_message.ack.assert_awaited_once()
    rabbitmq_message.reject.assert_not_awaited()
    rabbitmq_message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_publication_failure_requeues_original(
    monkeypatch: pytest.MonkeyPatch,
    rabbitmq_message: MagicMock,
) -> None:
    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        AsyncMock(
            side_effect=TimeoutError("SMTP timeout"),
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        AsyncMock(
            side_effect=ConnectionError("RabbitMQ unavailable"),
        ),
    )

    await process_email_job(rabbitmq_message)

    rabbitmq_message.nack.assert_awaited_once_with(
        requeue=True,
    )
    rabbitmq_message.ack.assert_not_awaited()
    rabbitmq_message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_maximum_retries_rejects_message(
    monkeypatch: pytest.MonkeyPatch,
    email_job: EmailJob,
    rabbitmq_message: MagicMock,
) -> None:
    exhausted_job = email_job.model_copy(
        update={"retry_count": 3},
    )

    rabbitmq_message.body = exhausted_job.model_dump_json().encode("utf-8")

    publish_retry_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        AsyncMock(
            side_effect=TimeoutError("SMTP timeout"),
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        publish_retry_mock,
    )

    await process_email_job(rabbitmq_message)

    publish_retry_mock.assert_not_awaited()
    rabbitmq_message.reject.assert_awaited_once_with(
        requeue=False,
    )
    rabbitmq_message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_permanent_smtp_failure(
    monkeypatch: pytest.MonkeyPatch,
    rabbitmq_message: MagicMock,
) -> None:
    from aiosmtplib.errors import SMTPAuthenticationError

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        AsyncMock(
            side_effect=SMTPAuthenticationError(
                535,
                "Authentication failed",
            ),
        ),
    )

    publish_retry_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        publish_retry_mock,
    )

    await process_email_job(rabbitmq_message)

    publish_retry_mock.assert_not_awaited()
    rabbitmq_message.reject.assert_awaited_once_with(
        requeue=False,
    )
    rabbitmq_message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_email_payload(
    rabbitmq_message: MagicMock,
) -> None:
    rabbitmq_message.body = b'{"invalid": "payload"}'

    await process_email_job(rabbitmq_message)

    rabbitmq_message.reject.assert_awaited_once_with(
        requeue=False,
    )
    rabbitmq_message.ack.assert_not_awaited()
    rabbitmq_message.nack.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_retry_count", "expected_retry_count"),
    [
        (0, 1),
        (1, 2),
        (2, 3),
    ],
)
async def test_retry_counter_increments(
    monkeypatch: pytest.MonkeyPatch,
    email_job: EmailJob,
    rabbitmq_message: MagicMock,
    current_retry_count: int,
    expected_retry_count: int,
) -> None:
    job = email_job.model_copy(
        update={"retry_count": current_retry_count},
    )

    rabbitmq_message.body = job.model_dump_json().encode("utf-8")

    publish_retry_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        AsyncMock(
            side_effect=TimeoutError("SMTP timeout"),
        ),
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        publish_retry_mock,
    )

    await process_email_job(rabbitmq_message)

    publish_retry_mock.assert_awaited_once()

    retry_job = publish_retry_mock.await_args.args[0]

    assert retry_job.retry_count == expected_retry_count

    rabbitmq_message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_email_is_not_sent(
    monkeypatch: pytest.MonkeyPatch,
    email_job: EmailJob,
    rabbitmq_message: MagicMock,
) -> None:
    expired_job = email_job.model_copy(
        update={
            "expires_at": datetime.now(UTC) - timedelta(minutes=1),
        },
    )

    rabbitmq_message.body = expired_job.model_dump_json().encode("utf-8")

    send_email_mock = AsyncMock()
    publish_retry_mock = AsyncMock()

    monkeypatch.setattr(
        "app.messaging.worker.send_email",
        send_email_mock,
    )
    monkeypatch.setattr(
        "app.messaging.worker.publish_retry",
        publish_retry_mock,
    )

    await process_email_job(rabbitmq_message)

    send_email_mock.assert_not_awaited()
    publish_retry_mock.assert_not_awaited()

    rabbitmq_message.ack.assert_awaited_once()
    rabbitmq_message.reject.assert_not_awaited()
