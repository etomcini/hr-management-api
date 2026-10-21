import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.dependencies.database import AsyncSessionLocal
from app.messaging.models import OutboxMessage, OutboxStatus

logger = logging.getLogger(__name__)

OUTBOX_RETENTION_HOURS = 24


async def cleanup_published_outbox() -> int:
    cutoff = datetime.now(UTC) - timedelta(
        hours=OUTBOX_RETENTION_HOURS,
    )

    async with AsyncSessionLocal() as db:
        stmt = (
            delete(OutboxMessage)
            .where(
                OutboxMessage.status == OutboxStatus.PUBLISHED.value,
                OutboxMessage.published_at < cutoff,
            )
            .returning(OutboxMessage.id)
        )

        result = await db.execute(stmt)
        deleted_ids = result.scalars().all()

        await db.commit()

    logger.info(
        "Deleted %s published outbox records",
        len(deleted_ids),
    )

    return len(deleted_ids)
