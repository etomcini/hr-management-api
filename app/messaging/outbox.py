from sqlalchemy.ext.asyncio import AsyncSession

from app.messaging.models import OutboxMessage
from app.messaging.schemas import EmailJob


def add_email_to_outbox(
    db: AsyncSession,
    job: EmailJob,
) -> OutboxMessage:
    message = OutboxMessage(
        id=job.job_id,
        event_type="email.send",
        payload=job.model_dump(mode="json"),
    )

    db.add(message)

    return message
