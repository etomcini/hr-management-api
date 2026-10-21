from urllib.parse import quote

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from app.core.config import settings

EMAIL_QUEUE = "hr.email.send"
EMAIL_FAILED_QUEUE = "hr.email.failed"

EMAIL_BUSY_QUEUE = "hr.email.busy.10s"

EMAIL_RETRY_DELAYS_MS = (30_000, 60_000, 120_000)

EMAIL_RETRY_QUEUES = (
    "hr.email.retry.30s",
    "hr.email.retry.60s",
    "hr.email.retry.120s",
)


def get_rabbitmq_url() -> str:
    username = quote(settings.rabbitmq_user, safe="")
    password = quote(
        settings.rabbitmq_password.get_secret_value(),
        safe="",
    )
    vhost = quote(settings.rabbitmq_vhost, safe="")

    return (
        f"amqp://{username}:{password}"
        f"@{settings.rabbitmq_host}:{settings.rabbitmq_port}/{vhost}"
    )


async def connect_rabbitmq() -> AbstractRobustConnection:
    return await aio_pika.connect_robust(
        get_rabbitmq_url(),
        timeout=10,
    )
