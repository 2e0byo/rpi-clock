import asyncio
from structlog import get_logger

import pytest

from rpi_clock.fadeable import SpiControllerError
from rpi_clock.hal import lamp

logger = get_logger()

@pytest.fixture(scope="module")
def hardware():
    yield


async def test_reset(hardware):
    # try to stuff up hardware
    stuffed_up = False
    for _ in range(5):
        lamp.spi_xfer(b"abcdefgasdf")
        try:
            lamp.duty = 112
        except SpiControllerError:
            stuffed_up = True
            break
    assert stuffed_up
    await lamp.set_duty(112)


async def test_set(hardware):
    await lamp.fade(percent_duty=1)
    await lamp.fade(percent_duty=0)


@pytest.mark.parametrize("rate", (1_000, 4_000, 8_000, 10_000))
async def test_no_reset(rate, hardware, mocker):
    lamp.spi.rate = rate
    called = 0
    reset = lamp.reset

    async def wrapper(*args, **kwargs):
        nonlocal called
        called += 1
        return await reset(*args, **kwargs)

    lamp.reset = wrapper
    await lamp.fade(percent_duty=1)
    await lamp.fade(percent_duty=0)
    assert not called
