import asyncio
import logging
from abc import ABC, abstractmethod
from time import monotonic, sleep
from typing import Optional

import pigpio


class Fadeable(ABC):
    """Base Class for a fadeable output."""

    instances = []
    MAX_FADE_FREQ_HZ = 90  # no point updating faster than this.

    def __init__(self, *args, **kwargs):
        name = kwargs.get("name", f"{__name__}-{len(self.instances)}")
        self.instances.append(name)
        self._logger = logging.getLogger(name)
        self.duty = 0
        self._fade_task = None

    async def fade(
        self,
        *,
        duty: int = None,
        percent_duty: float = None,
        duration: int = 1,
    ):
        self.cancel_fade()
        self._fade_task = asyncio.create_task(self._fade(duty, percent_duty, duration))
        await self._fade_task
        self._fade_task = None

    def cancel_fade(self):
        if self._fade_task:
            self._fade_task.cancel()

    async def set_duty(self, val: int):
        self.duty = val

    async def _fade(
        self,
        duty: int = None,
        percent_duty: float = None,
        duration: int = 1,
    ):

        if duty is None and percent_duty is None:
            raise ValueError("One of duty or percent_duty needs to be supplied!")

        duty = duty if duty is not None else self._convert_duty(percent_duty)
        current = self.duty
        if duty == current:
            return
        step = 1 if current < duty else -1
        steps = abs(current - duty)
        freq = steps / duration
        while freq > self.MAX_FADE_FREQ_HZ:
            steps //= 2
            step *= 2
            freq = steps / duration

        delay = 1 / freq

        for br in range(current, duty + step, step):
            start = monotonic()
            br = max(br, 0)
            br = min(br, self.max_duty)
            await self.set_duty(br)
            elapsed = monotonic() - start
            await asyncio.sleep(max(0, delay - elapsed))
        await self.set_duty(br)

    @property
    def percent_duty(self) -> float:
        return self.duty / self.max_duty

    @percent_duty.setter
    def percent_duty(self, val: float):
        val = self._convert_duty(val)
        self.duty = val

    def _convert_duty(self, val: float) -> int:
        if val < 0:
            return 0
        elif val > 1:
            return self.max_duty
        else:
            return round(val * self.max_duty)

    @property
    @abstractmethod
    def duty(self):
        pass  # pragma: no cover


class PWM(Fadeable):
    """A fadeable pwm output."""

    def __init__(
        self, pin, pi, *args, freq: int = 10_000, max_duty: int = 50, **kwargs
    ):
        self.pin = pin
        self.max_duty = max_duty
        self.pi = pi
        pi.set_mode(self.pin, 1)
        pi.set_PWM_frequency(self.pin, freq)
        pi.set_PWM_range(self.pin, self.max_duty)
        super().__init__(*args, **kwargs)
        self._logger.debug(f"Started pwm on pin {self.pin}.")

    @property
    def duty(self):
        return self.pi.get_PWM_dutycycle(self.pin)

    @duty.setter
    def duty(self, val: int):
        self.pi.set_PWM_dutycycle(self.pin, val)


class SpiError(Exception):
    """An error with spi communication."""


class Lamp(Fadeable):
    """An SPI controlled lamp."""

    SETTLE_TIME_S = 0.001
    SPI_ATTEMPTS = 12

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
        self.spi_open()
        self._duty = None
        super().__init__(*args, **kwargs)

    @staticmethod
    def _convert(b: bytes):
        return int.from_bytes(b, "little")

    def spi_xfer(self, data):
        return self.pi.bb_spi_xfer(self.cs, data)

    @property
    def duty(self):
        return self._duty

    def get_hardware_duty(self):
        self.spi_xfer(b"r")
        sleep(self.SETTLE_TIME_S)
        return self._convert(self.spi_xfer([0] * 2)[1])

    @duty.setter
    def duty(self, val: int):
        duty = int(val).to_bytes(2, "little")
        self.spi_xfer(b"s" + duty)
        sleep(self.SETTLE_TIME_S)
        resp = self._convert(self.spi_xfer([0] * 2)[1])
        if resp != val:
            raise SpiError(f"Failed to set lamp to {val}")
        self._duty = val

    def spi_open(self):
        self.pi.bb_spi_open(
            self.cs, self.miso, self.mosi, self.sclk, self.baud, self.mode
        )

    def spi_close(self):
        self.pi.bb_spi_close(self.cs)

    async def reset(self, long_=False):
        self._logger.debug("Resetting")
        self.pi.write(self.cs, 0)
        await asyncio.sleep(3)
        self.pi.write(self.cs, 1)
        await asyncio.sleep(self.SETTLE_TIME_S)
        self.spi_xfer([0] * 6)  # flush buffer: something isn't resetting properly...

    async def set_duty(self, val: int):
        for attempt in range(self.SPI_ATTEMPTS):
            try:
                self.duty = val
                if attempt > 1:
                    self._logger.debug(f"Set lamp to {val} after {attempt} attempts.")
                return
            except SpiError:
                if attempt == 4:
                    # if attempt and not attempt % 4:
                    await self.reset()
                else:
                    await asyncio.sleep(
                        0.3 * attempt
                    )  # backing off is enough most of the time.

        raise SpiError(f"Failed to set lamp to {val}")

    def __del__(self):
        try:
            self.spi_close()
        except Exception:
            pass
