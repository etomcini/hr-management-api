from aio_pika.abc import (
    AbstractChannel,
    AbstractQueue,
)

from app.messaging.connection import (
    EMAIL_BUSY_QUEUE,
    EMAIL_FAILED_QUEUE,
    EMAIL_QUEUE,
    EMAIL_RETRY_DELAYS_MS,
    EMAIL_RETRY_QUEUES,
)


async def declare_email_queue(
    channel: AbstractChannel,
) -> AbstractQueue:
    # Queue for messages that cannot be delivered.
    await channel.declare_queue(
        EMAIL_FAILED_QUEUE,
        durable=True,
    )

    # Retry queues send expired messages back to the main queue.
    for queue_name, delay_ms in zip(
        EMAIL_RETRY_QUEUES,
        EMAIL_RETRY_DELAYS_MS,
        strict=True,
    ):
        await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-message-ttl": delay_ms,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": EMAIL_QUEUE,
            },
        )

    # BUSY queue delays messages while another worker
    # holds an active PostgreSQL delivery claim.
    await channel.declare_queue(
        EMAIL_BUSY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 10_000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": EMAIL_QUEUE,
        },
    )

    # Preserve the existing main queue configuration.
    return await channel.declare_queue(
        EMAIL_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": EMAIL_FAILED_QUEUE,
        },
    )
