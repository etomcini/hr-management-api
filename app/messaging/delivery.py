from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.dependencies.database import AsyncSessionLocal
from app.messaging.delivery_models import (
    EmailDelivery,
    EmailDeliveryStatus,
)

CLAIM_SECONDS = 120


class ClaimResult(StrEnum):
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    BUSY = "busy"


@dataclass(frozen=True)
class EmailClaim:
    result: ClaimResult
    claim_id: UUID | None = None


async def claim_email_job(job_id: UUID) -> EmailClaim:
    now = datetime.now(UTC)
    claim_id = uuid4()
    claimed_until = now + timedelta(seconds=CLAIM_SECONDS)

    async with AsyncSessionLocal.begin() as db:
        stmt = (
            insert(EmailDelivery)
            .values(
                job_id=job_id,
                status=EmailDeliveryStatus.PROCESSING.value,
                attempts=1,
                claim_id=claim_id,
                claimed_until=claimed_until,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=[EmailDelivery.job_id],
                set_={
                    "claim_id": claim_id,
                    "claimed_until": claimed_until,
                    "attempts": EmailDelivery.attempts + 1,
                },
                where=(
                    (EmailDelivery.status == EmailDeliveryStatus.PROCESSING.value)
                    & or_(
                        EmailDelivery.claimed_until.is_(None),
                        EmailDelivery.claimed_until <= now,
                    )
                ),
            )
            .returning(EmailDelivery.claim_id)
        )

        acquired_id = await db.scalar(stmt)

        if acquired_id is not None:
            return EmailClaim(
                result=ClaimResult.CLAIMED,
                claim_id=acquired_id,
            )

        status = await db.scalar(
            select(EmailDelivery.status).where(
                EmailDelivery.job_id == job_id,
            )
        )

        if status == EmailDeliveryStatus.DELIVERED.value:
            return EmailClaim(result=ClaimResult.DELIVERED)

        if status == EmailDeliveryStatus.PROCESSING.value:
            return EmailClaim(result=ClaimResult.BUSY)

        raise RuntimeError("Unexpected email delivery state")


async def mark_email_delivered(
    job_id: UUID,
    claim_id: UUID,
) -> bool:
    now = datetime.now(UTC)

    async with AsyncSessionLocal.begin() as db:
        stmt = (
            update(EmailDelivery)
            .where(
                EmailDelivery.job_id == job_id,
                EmailDelivery.claim_id == claim_id,
                EmailDelivery.status == EmailDeliveryStatus.PROCESSING.value,
                EmailDelivery.claimed_until > now,
            )
            .values(
                status=EmailDeliveryStatus.DELIVERED.value,
                delivered_at=now,
                claimed_until=None,
                claim_id=None,
            )
            .returning(EmailDelivery.job_id)
        )

        updated_id = await db.scalar(stmt)

        return updated_id is not None


async def release_email_claim(
    job_id: UUID,
    claim_id: UUID,
) -> bool:
    async with AsyncSessionLocal.begin() as db:
        stmt = (
            update(EmailDelivery)
            .where(
                EmailDelivery.job_id == job_id,
                EmailDelivery.claim_id == claim_id,
                EmailDelivery.status == EmailDeliveryStatus.PROCESSING.value,
            )
            .values(
                claim_id=None,
                claimed_until=datetime.now(UTC),
            )
            .returning(EmailDelivery.job_id)
        )

        released_id = await db.scalar(stmt)

        return released_id is not None
