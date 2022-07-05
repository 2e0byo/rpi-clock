import asyncio
import logging

import coloredlogs
import pytest

from rpi_clock.fadeable import SpiControllerError
from rpi_clock.hal import lamp

coloredlogs.install(level=logging.DEBUG)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def hardware():
    yield
    lamp.spi_close()


async def test_reset(hardware):
    # try to stuff up hardware
    stuffed_up = False
    for _ in range(5):
        lamp.pi.bb_spi_xfer(lamp.cs, b"abcdefgasdf")
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
