import asyncio
import logging

import aiosmtplib
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from app.email.sender import send_email
from app.messaging.busy import publish_busy
from app.messaging.connection import (
    EMAIL_QUEUE,
    connect_rabbitmq,
)
from app.messaging.delivery import (
    ClaimResult,
    claim_email_job,
    mark_email_delivered,
    release_email_claim,
)
from app.messaging.retry import publish_retry
from app.messaging.schemas import EmailJob, is_email_job_expired
from app.messaging.topology import declare_email_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_retryable_smtp_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            aiosmtplib.errors.SMTPConnectError,
            aiosmtplib.errors.SMTPServerDisconnected,
            TimeoutError,
            ConnectionError,
        ),
    ):
        return True

    if isinstance(exc, aiosmtplib.errors.SMTPResponseException):
        return 400 <= exc.code < 500

    return False


async def process_email_job(
    message: AbstractIncomingMessage,
) -> None:
    try:
        job = EmailJob.model_validate_json(message.body)
    except ValidationError:
        logger.error("Invalid email job payload")
        await message.reject(requeue=False)
        return

    if is_email_job_expired(job):
        logger.info("Skipping expired email job %s", job.job_id)
        await message.ack()
        return

    # PostgreSQL must be available before SMTP delivery.
    try:
        claim = await claim_email_job(job.job_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Could not claim email job %s",
            job.job_id,
        )
        await message.nack(requeue=True)
        return

    if claim.result == ClaimResult.DELIVERED:
        logger.info(
            "Duplicate email job %s already delivered",
            job.job_id,
        )
        await message.ack()
        return

    if claim.result == ClaimResult.BUSY:
        logger.info(
            "Email job %s is currently owned by another worker",
            job.job_id,
        )

        try:
            await publish_busy(job)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Failed to defer BUSY email job %s",
                job.job_id,
            )

            # Keep the original message if the delayed
            # publication could not be confirmed.
            await message.nack(requeue=True)
            return

        # The delayed copy has been confirmed by RabbitMQ.
        await message.ack()
        return

    if claim.claim_id is None:
        raise RuntimeError("Claimed job has no claim ID")

    claim_id = claim.claim_id

    # Check again after acquiring the database claim.
    if is_email_job_expired(job):
        try:
            await release_email_claim(job.job_id, claim_id)
        except Exception:
            logger.exception(
                "Could not release expired job %s",
                job.job_id,
            )
            await message.nack(requeue=True)
            return

        await message.ack()
        return

    try:
        logger.info(
            "Sending email job %s (attempt %s/4)",
            job.job_id,
            job.retry_count + 1,
        )

        async with asyncio.timeout(60):
            await send_email(
                to_email=job.recipient,
                subject=job.subject,
                text_content=job.text_content,
                html_content=job.html_content,
            )

    except asyncio.CancelledError:
        # Shutdown or task cancellation: release the claim.
        try:
            await release_email_claim(job.job_id, claim_id)
        except Exception:
            logger.exception(
                "Failed to release cancelled job %s",
                job.job_id,
            )
        raise

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "SMTP delivery failed for job %s",
            job.job_id,
        )

        # Do not ACK or schedule another attempt until
        # the current database claim has been released.
        try:
            released = await release_email_claim(
                job.job_id,
                claim_id,
            )
        except Exception:
            logger.exception(
                "Could not release claim for job %s",
                job.job_id,
            )
            await message.nack(requeue=True)
            return

        if not released:
            logger.error(
                "Claim ownership lost for job %s",
                job.job_id,
            )
            await message.nack(requeue=True)
            return

        if is_retryable_smtp_error(exc) and job.retry_count < 3:
            retry_job = job.model_copy(
                update={"retry_count": job.retry_count + 1},
            )

            try:
                await publish_retry(retry_job)
            except Exception:
                logger.exception(
                    "Failed to publish retry for job %s",
                    job.job_id,
                )
                await message.nack(requeue=True)
                return

            await message.ack()
            return

        await message.reject(requeue=False)
        return

    # SMTP accepted the message.
    # Persist delivery before acknowledging RabbitMQ.
    try:
        recorded = await mark_email_delivered(
            job.job_id,
            claim_id,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Could not record successful delivery for %s",
            job.job_id,
        )
        await message.nack(requeue=True)
        return

    if not recorded:
        logger.error(
            "Delivery claim expired or ownership lost for %s",
            job.job_id,
        )
        await message.nack(requeue=True)
        return

    await message.ack()

    logger.info(
        "Email job delivered successfully: %s",
        job.job_id,
    )


async def run_worker() -> None:
    connection = await connect_rabbitmq()

    try:
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)

            queue = await declare_email_queue(channel)

            logger.info(
                "Email worker listening on %s",
                EMAIL_QUEUE,
            )

            await queue.consume(
                process_email_job,
                no_ack=False,
            )

            await asyncio.Future()
    finally:
        if not connection.is_closed:
            await connection.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
