from contextlib import asynccontextmanager
from typing import AsyncIterator

from . import clock, hal


@asynccontextmanager
async def setup_hardware(_) -> AsyncIterator[None]:
    hal.mute.off()

    await hal.backlight.start()
    await hal.lamp.start()
    await hal.volume.start()
    await clock.run()

    yield
