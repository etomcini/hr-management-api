from datetime import UTC, datetime, timedelta

MAX_OUTBOX_ATTEMPTS = 10
MAX_RETRY_DELAY_SECONDS = 300


def calculate_outbox_retry_at(
    attempt_count: int,
    *,
    now: datetime | None = None,
) -> datetime:
    current_time = now or datetime.now(UTC)

    delay_seconds = min(
        2 ** min(attempt_count, 9),
        MAX_RETRY_DELAY_SECONDS,
    )

    return current_time + timedelta(
        seconds=delay_seconds,
    )
