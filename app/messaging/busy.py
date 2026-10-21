import aio_pika

from app.messaging.connection import (
    EMAIL_BUSY_QUEUE,
    connect_rabbitmq,
)
from app.messaging.schemas import EmailJob
from app.messaging.topology import declare_email_queue


async def publish_busy(job: EmailJob) -> None:
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
                routing_key=EMAIL_BUSY_QUEUE,
                mandatory=True,
            )

    finally:
        await connection.close()
