import asyncio
import logging
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import or_, select

from app.dependencies.database import AsyncSessionLocal
from app.messaging.cleanup import cleanup_published_outbox
from app.messaging.models import OutboxMessage, OutboxStatus
from app.messaging.outbox_retry import (
    MAX_OUTBOX_ATTEMPTS,
    calculate_outbox_retry_at,
)
from app.messaging.publisher import publish_email_job
from app.messaging.schemas import (
    EmailJob,
    is_email_job_expired,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
BATCH_SIZE = 20
CLEANUP_INTERVAL_SECONDS = 3600


async def process_outbox_batch() -> int:
    published_count = 0
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as db, db.begin():
        stmt = (
            select(OutboxMessage)
            .where(
                OutboxMessage.status == OutboxStatus.PENDING.value,
                or_(
                    OutboxMessage.next_attempt_at.is_(None),
                    OutboxMessage.next_attempt_at <= now,
                ),
            )
            .order_by(
                OutboxMessage.created_at,
                OutboxMessage.id,
            )
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )

        result = await db.scalars(stmt)
        messages = result.all()

        for message in messages:
            if message.event_type != "email.send":
                message.status = OutboxStatus.FAILED.value
                message.last_error = "unsupported_event_type"

                logger.error(
                    "Unsupported outbox event type: %s",
                    message.id,
                )
                continue

            try:
                job = EmailJob.model_validate(
                    message.payload,
                )

                if is_email_job_expired(job):
                    logger.info(
                        "Skipping expired outbox message %s",
                        message.id,
                    )

                    # Mark it as handled so it is not retried forever.
                    message.published_at = datetime.now(UTC)
                    continue

            except ValidationError:
                message.status = OutboxStatus.FAILED.value
                message.last_error = "invalid_email_payload"

                logger.error(
                    "Invalid email payload: %s",
                    message.id,
                )
                continue

            if is_email_job_expired(job):
                message.status = OutboxStatus.EXPIRED.value
                message.next_attempt_at = None

                logger.info(
                    "Outbox message expired: %s",
                    message.id,
                )
                continue

            message.attempt_count += 1

            try:
                await publish_email_job(job)

            except asyncio.CancelledError:
                raise

            except Exception:  # noqa: BLE001
                # Avoid logging exception details because they
                # could contain sensitive email information.
                message.last_error = "rabbitmq_publish_error"

                if message.attempt_count >= MAX_OUTBOX_ATTEMPTS:
                    message.status = OutboxStatus.FAILED.value
                    message.next_attempt_at = None

                    logger.error(
                        "Outbox message %s failed after %s attempts",
                        message.id,
                        message.attempt_count,
                    )
                else:
                    message.next_attempt_at = calculate_outbox_retry_at(
                        message.attempt_count,
                    )

                    logger.warning(
                        "Outbox message %s scheduled for retry",
                        message.id,
                    )

                continue

            message.status = OutboxStatus.PUBLISHED.value
            message.published_at = datetime.now(UTC)
            message.next_attempt_at = None
            message.last_error = None

            published_count += 1

            logger.info(
                "Outbox message published: %s",
                message.id,
            )

    return published_count


async def run_outbox_worker() -> None:
    logger.info("Outbox publisher started")

    loop = asyncio.get_running_loop()
    next_cleanup = loop.time() + CLEANUP_INTERVAL_SECONDS

    while True:
        try:
            await process_outbox_batch()

            if loop.time() >= next_cleanup:
                await cleanup_published_outbox()
                next_cleanup = loop.time() + CLEANUP_INTERVAL_SECONDS

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Outbox processing failed")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        asyncio.run(run_outbox_worker())
    except KeyboardInterrupt:
        logger.info("Outbox publisher stopped")
