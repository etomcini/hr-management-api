import aio_pika

from app.messaging.connection import (
    EMAIL_RETRY_QUEUES,
    connect_rabbitmq,
)
from app.messaging.schemas import EmailJob
from app.messaging.topology import declare_email_queue


async def publish_retry(job: EmailJob) -> None:
    # retry_count=1 -> 30s queue
    # retry_count=2 -> 60s queue
    # retry_count=3 -> 120s queue
    queue_name = EMAIL_RETRY_QUEUES[job.retry_count - 1]

    connection = await connect_rabbitmq()

    try:
        async with connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        ) as channel:
            await declare_email_queue(channel)

            message = aio_pika.Message(
                body=job.model_dump_json().encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(job.job_id),
            )

            await channel.default_exchange.publish(
                message,
                routing_key=queue_name,
                mandatory=True,
            )

    finally:
        await connection.close()
