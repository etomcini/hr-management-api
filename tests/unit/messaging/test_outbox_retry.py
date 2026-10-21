from datetime import UTC, datetime, timedelta

import pytest

from app.messaging.outbox_retry import (
    calculate_outbox_retry_at,
)


@pytest.mark.parametrize(
    ("attempt_count", "expected_seconds"),
    [
        (1, 2),
        (2, 4),
        (3, 8),
        (4, 16),
        (5, 32),
        (6, 64),
        (7, 128),
        (8, 256),
        (9, 300),
        (10, 300),
    ],
)
def test_calculate_outbox_retry_at(
    attempt_count: int,
    expected_seconds: int,
) -> None:
    now = datetime(2026, 10, 20, tzinfo=UTC)

    result = calculate_outbox_retry_at(
        attempt_count,
        now=now,
    )

    assert result == now + timedelta(
        seconds=expected_seconds,
    )
