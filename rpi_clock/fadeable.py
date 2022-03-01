import asyncio
from typing import Optional

import apigpio


class Fadeable:
    """Base Class for a fadeable output."""

    def __init__(self, *args, **kwargs):
        self.duty = 0
        self.fade_delay = 0.01

    async def fade(self, val: int, duration: int = 0):
        current = self.duty
        step = 1 if current < val else -1
        delay = duration / abs(current - val) if duration else self.fade_delay
        for br in range(current, val + step, step):
            self.duty = br
            await asyncio.sleep(delay)

    async def percent_duty(self, val: int = None):
        if val is None:
            return await self.duty() / self.max_duty

        if val < 0:
            await self.duty(0)
        elif val > 1:
            await self.duty(self.max_duty)
        else:
            await self.duty(round(val * self.max_duty))


class PWM(Fadeable):
    """A fadeable pwm output."""

    MAX_DUTY = 50
    FREQ = 10000

    def __init__(
        self, pin, pi, *args, freq: int = None, max_duty: int = None, **kwargs
    ):
        self.pin = pin
        self.max_duty = max_duty or self.MAX_DUTY
        self.pi = pi
        asyncio.create_task(self._start())
        super().__init__(*args, **kwargs)

    async def _start(self):
        await self.pi.set_mode(self.pin, 1)
        await self.pi.set_PWM_frequency(self.pin, freq or self.FREQ)
        await self.pi.set_PWM_range(self.pin, self.max_duty)

    async def duty(self, val: int = None) -> int:
        if val is None:
            return await self.pi.get_PWM_dutycycle(self.pin)

        await self.pi.set_PWM_dutycycle(self.pin, val)


class Lamp(Fadeable):
    """An SPI controlled lamp."""

    def __init__(
        self,
        pi,
        *args,
        cs: int = 8,
        miso: int = 9,
        mosi: int = 10,
        sclk: int = 11,
        baud: int = 10_000,
        mode: int = 1,
        **kwargs,
    ):
        self.cs = cs
        self.miso = miso
        self.mosi = mosi
        self.sclk = sclk
        self.baud = baud
        self.mode = mode
        self.max_duty = 1023
        self.pi = pi
        asyncio.create_task(self._start())
        super().__init__(*args, **kwargs)

    async def _start(self):
        await self.pi.bb_spi_open(
            self.cs, self.miso, self.mosi, self.sclk, self.baud, self.mode
        )

    @staticmethod
    def _convert(b: bytes):
        return int.from_bytes(b, "little")

    async def duty(self, val: int = None) -> Optional[int]:
        if val is None:
            await self.pi.bb_spi_xfer(self.cs, b"r")
            await asyncio.sleep(0.001)
            return convert(await self.pi.bb_spi_xfer(self.cs, [0] * 2)[1])

        val = int(val).to_bytes(2, "little")
        for _ in range(self.ATTEMPTS):
            await self.pi.bb_spi_xfer(self.cs, b"s" + val)
            await asyncio.sleep(0.001)
            resp = self._convert(await self.pi.bb_spi_xfer(self.cs, [0] * 2)[1])
            if resp == val:
                return

    def __del__(self):
        asyncio.create_task(self.pi.bb_spi_close(self.cs))
