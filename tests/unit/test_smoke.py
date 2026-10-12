import pytest


@pytest.mark.unit
def test_pytest_configuration() -> None:
    assert 2 + 2 == 4


@pytest.mark.unit
async def test_async_pytest_configuration() -> None:
    async def get_value() -> int:
        return 42

    assert await get_value() == 42
