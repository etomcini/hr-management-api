import asyncio
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from app.dependencies.database import AsyncSessionLocal
from app.messaging.delivery import (
    ClaimResult,
    claim_email_job,
    mark_email_delivered,
    release_email_claim,
)
from app.messaging.delivery_models import (
    EmailDelivery,
    EmailDeliveryStatus,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def delivery_job_id() -> AsyncGenerator[Callable[[], UUID]]:
    job_ids: list[UUID] = []

    def create_job_id() -> UUID:
        job_id = uuid4()
        job_ids.append(job_id)
        return job_id

    try:
        yield create_job_id
    finally:
        if job_ids:
            async with AsyncSessionLocal.begin() as db:
                await db.execute(
                    delete(EmailDelivery).where(EmailDelivery.job_id.in_(job_ids))
                )


async def get_delivery(job_id):
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(EmailDelivery).where(
                EmailDelivery.job_id == job_id,
            )
        )


async def expire_claim(job_id) -> None:
    async with AsyncSessionLocal.begin() as db:
        await db.execute(
            update(EmailDelivery)
            .where(EmailDelivery.job_id == job_id)
            .values(claimed_until=datetime.now(UTC) - timedelta(seconds=1))
        )


async def test_first_claim_creates_delivery_record(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    claim = await claim_email_job(job_id)

    assert claim.result == ClaimResult.CLAIMED
    assert claim.claim_id is not None

    delivery = await get_delivery(job_id)

    assert delivery is not None
    assert delivery.status == EmailDeliveryStatus.PROCESSING.value
    assert delivery.attempts == 1
    assert delivery.claim_id == claim.claim_id


async def test_concurrent_claims_allow_only_one_owner(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    results = await asyncio.gather(
        claim_email_job(job_id),
        claim_email_job(job_id),
        claim_email_job(job_id),
        claim_email_job(job_id),
        claim_email_job(job_id),
    )

    claimed = [result for result in results if result.result == ClaimResult.CLAIMED]

    busy = [result for result in results if result.result == ClaimResult.BUSY]

    assert len(claimed) == 1
    assert len(busy) == 4
    assert claimed[0].claim_id is not None
    assert all(result.claim_id is None for result in busy)

    delivery = await get_delivery(job_id)

    assert delivery is not None
    assert delivery.attempts == 1
    assert delivery.claim_id == claimed[0].claim_id


async def test_active_claim_cannot_be_stolen(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)
    second = await claim_email_job(job_id)

    assert first.result == ClaimResult.CLAIMED
    assert second.result == ClaimResult.BUSY
    assert second.claim_id is None


async def test_expired_claim_can_be_reclaimed(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)

    await expire_claim(job_id)

    second = await claim_email_job(job_id)

    assert second.result == ClaimResult.CLAIMED
    assert second.claim_id is not None
    assert second.claim_id != first.claim_id

    delivery = await get_delivery(job_id)

    assert delivery is not None
    assert delivery.attempts == 2
    assert delivery.claim_id == second.claim_id


async def test_old_claim_cannot_mark_new_claim_delivered(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)

    await expire_claim(job_id)

    second = await claim_email_job(job_id)

    old_owner_result = await mark_email_delivered(
        job_id,
        first.claim_id,
    )

    assert old_owner_result is False

    new_owner_result = await mark_email_delivered(
        job_id,
        second.claim_id,
    )

    assert new_owner_result is True

    delivery = await get_delivery(job_id)

    assert delivery.status == EmailDeliveryStatus.DELIVERED.value
    assert delivery.delivered_at is not None


async def test_delivered_job_cannot_be_claimed_again(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)

    recorded = await mark_email_delivered(
        job_id,
        first.claim_id,
    )

    assert recorded is True

    second = await claim_email_job(job_id)

    assert second.result == ClaimResult.DELIVERED
    assert second.claim_id is None

    delivery = await get_delivery(job_id)

    assert delivery.attempts == 1


async def test_released_claim_can_be_reclaimed(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)

    released = await release_email_claim(
        job_id,
        first.claim_id,
    )

    assert released is True

    second = await claim_email_job(job_id)

    assert second.result == ClaimResult.CLAIMED
    assert second.claim_id != first.claim_id

    delivery = await get_delivery(job_id)

    assert delivery.attempts == 2


async def test_worker_crash_before_smtp_allows_recovery(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    # Worker A claims the job.
    first = await claim_email_job(job_id)

    assert first.result == ClaimResult.CLAIMED

    # Simulate Worker A crashing:
    # no SMTP call, no release, no completion.
    await expire_claim(job_id)

    # Worker B recovers the abandoned job.
    recovered = await claim_email_job(job_id)

    assert recovered.result == ClaimResult.CLAIMED
    assert recovered.claim_id != first.claim_id

    recorded = await mark_email_delivered(
        job_id,
        recovered.claim_id,
    )

    assert recorded is True

    delivery = await get_delivery(job_id)

    assert delivery.status == EmailDeliveryStatus.DELIVERED.value
    assert delivery.attempts == 2


async def test_crash_after_smtp_can_require_redelivery(
    delivery_job_id: Callable[[], UUID],
):
    job_id = delivery_job_id()

    first = await claim_email_job(job_id)

    # SMTP may have accepted the email here.
    # Simulate a crash before mark_email_delivered().
    await expire_claim(job_id)

    second = await claim_email_job(job_id)

    assert second.result == ClaimResult.CLAIMED
    assert second.claim_id != first.claim_id

    delivery = await get_delivery(job_id)

    assert delivery.status == EmailDeliveryStatus.PROCESSING.value
    assert delivery.attempts == 2
