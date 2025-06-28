import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from . import clock, hal, mqtt


@asynccontextmanager
async def setup_hardware(_) -> AsyncIterator[None]:
    hal.mute.off()

    await hal.backlight.start()
    await hal.lamp.start()
    await hal.volume.start()
    # acquiring the native gpio pin for reset breaks something in the kernel lcd driver.
    # resetting here fixes it.
    hal.lcd.restart()
    asyncio.get_event_loop().create_task(clock.run())

    await mqtt.handler.setup_mqtt()

    yield
