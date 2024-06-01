import asyncio
from abc import ABC, abstractmethod
from time import monotonic, sleep
from typing import Optional
from unittest.mock import Mock

from gpiozero import SPI, Device
from gpiozero.exc import SPIFixedRate
from gpiozero.pins import Factory
from rpi_hardware_pwm import HardwarePWM
from structlog import get_logger

from .endpoint import Endpoint

logger = get_logger()

class Fadeable(ABC):
    """Base Class for a fadeable output."""

    instances = []
    max_duty: int

    def __init__(self, *, max_fade_freq_hz: int = 50, name: Optional[str] = None):
        """Initialise a new fadeable object."""
        name = name or f"{__name__}-{len(self.instances)}"
        self.instances.append(name)
        self._logger = logger.bind(name=name)
        self.max_fade_freq_hz = max_fade_freq_hz
        self._fade_task = None
        self._duty = None
        self._zero_task = asyncio.get_event_loop().create_task(self._zero())
        self._fade_lock = asyncio.Lock()

    async def fade(
        self,
        *,
        duty: int | None = None,
        percent_duty: float | None = None,
        duration: int = 1,
    ):
        """Fade from current state in a given time."""
        if duty is None and percent_duty is None:
            raise ValueError("One of percent_duty or duty must be supplied.")

        async with self._fade_lock:
            self.cancel_fade()
            self._fade_task = asyncio.create_task(
                self._fade(duty, percent_duty, duration)
            )
            await self._fade_task
            self._fade_task = None

    def cancel_fade(self):
        """Cancel a running fade.  Not guaranteed to succeed immediately."""
        if self._fade_task:
            self._fade_task.cancel()

    async def _zero(self):
        if self._duty is None:
            await self.set_duty(0)

    async def set_duty(self, val: int):
        """Set duty."""
        val = max(min(self.max_duty, val), 0)
        await self.set_hardware_duty(val)
        self._duty = val

    async def get_duty(self) -> int:
        """Get duty."""
        return await self.get_hardware_duty()

    @abstractmethod
    async def set_hardware_duty(self, val: int):
        """Set duty in hardware."""

    @abstractmethod
    async def get_hardware_duty(self) -> int:
        """Get duty from hardware."""

    async def _fade(
        self,
        duty: int | None = None,
        percent_duty: float | None = None,
        duration: int = 1,
    ):

        if duty is None and percent_duty is None:
            raise ValueError("One of duty or percent_duty needs to be supplied!")

        if duty is None:
            assert percent_duty
            duty = self._convert_duty(percent_duty)
        current = await self.get_duty()
        if duty == current:
            return
        step = 1 if current < duty else -1
        steps = abs(current - duty)
        freq = steps / duration
        while freq > self.max_fade_freq_hz:
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

    async def get_percent_duty(self) -> float:
        """Get current duty as a percentage."""
        return await self.get_duty() / self.max_duty

    async def set_percent_duty(self, val: float):
        """Set current duty as a percentage."""
        val = self._convert_duty(val)
        await self.set_duty(val)

    def _convert_duty(self, val: float) -> int:
        if val < 0:
            return 0
        elif val > 1:
            return self.max_duty
        else:
            return round(val * self.max_duty)


class MockFadeable(Fadeable):
    """A fadeable with the output mocked."""

    def __init__(self, *args, **kwargs):
        """Initialise a new MockFadeable."""
        self.max_duty = 100
        self.set_duty_mock = Mock()
        self.get_duty_mock = Mock()
        # Generally when mocking we don't want anything funny happening with fading.
        kwargs["max_fade_freq_hz"] = kwargs.get("max_fade_freq_hz", 1_000_000_000)
        super().__init__(*args, **kwargs)
        self.set_duty_mock = Mock()  # replace as set_duty called in `__init__()`.

    async def set_hardware_duty(self, val: int):
        """Set the mocked duty and call the mock."""
        self.set_duty_mock(val)
        self.get_duty_mock.return_value = val

    async def get_hardware_duty(self) -> int:
        """Get the mocked duty and call the mock."""
        return self.get_duty_mock()


class PWM(Fadeable):
    """A fadeable pwm output using system pwm."""

    def __init__(
        self,
        channel: int,
        *args,
        freq: int = 1_000_000,
        **kwargs,
    ):
        """Initialise a new pwm fadeable object."""
        self.channel = channel
        self.pwm = HardwarePWM(channel, freq)
        self.max_duty = 100
        self.pwm.start(0)
        super().__init__(*args, **kwargs)
        self._logger.debug(f"Started pwm on channel {self.channel}.")

    async def get_hardware_duty(self):
        """Get the current raw duty cycle."""
        return self.pwm._duty_cycle

    async def set_hardware_duty(self, val: int):
        """Set the raw duty cycle."""
        self.pwm.change_duty_cycle(val)


class SpiControllerError(Exception):
    """An error with spi communication."""


class Lamp(Fadeable):
    """An SPI controlled lamp."""

    SETTLE_TIME_S = 0.001
    SPI_ATTEMPTS = 12

    def __init__(
        self,
        *args,
        cs: int = 8,
        miso: int = 9,
        mosi: int = 10,
        sclk: int = 11,
        baud: int = 10_000,
        mode: int = 1,
        pin_factory: Factory = None,
        **kwargs,
    ):
        """Initialise a new `Lamp` object."""
        # This is bad, but the suggested 'better' alternative is to call a
        # classmethod which *mututes the class state* with the result of this
        # call, and then look up the resulting attribute. No comment.
        pin_factory = pin_factory or Device._default_pin_factory()
        spi = pin_factory.spi(
            select_pin=cs, miso_pin=miso, mosi_pin=mosi, clock_pin=sclk
        )
        spi.clock_mode = mode
        try:
            spi.rate = baud
            rate_error = None
        except SPIFixedRate:
            rate_error = "Unable to set spi baud rate: implementation is fixed-rate."
        self.spi: SPI = spi
        self.cs = pin_factory.pin(cs)
        self.cs.function = "output"
        self.cs.state = 1
        self.max_duty = 1023
        self._hardware_lock = asyncio.Lock()
        super().__init__(*args, **kwargs)
        if rate_error:
            self._logger.error(rate_error)

    @staticmethod
    def _convert(b: bytes):
        return int.from_bytes(b, "little")

    def spi_xfer(self, data: bytes) -> bytes:
        """
        Transfer data to and from the controller over spi.

        This method abstracts from a particular spi driver.
        """
        return self.spi.transfer(data)

    async def get_duty(self):
        """Get the current duty."""
        return self._duty

    async def get_hardware_duty(self):
        """Get the current duty directly from the controller."""
        async with self._hardware_lock:
            self.spi_xfer(b"r")
            sleep(self.SETTLE_TIME_S)
            return self._convert(self.spi_xfer([0] * 2))

    async def reset(self):
        """Reset the controller."""
        self._logger.debug("Resetting")
        self.cs.state = 0
        await asyncio.sleep(3)
        self.cs.state = 1

    async def set_hardware_duty(self, val: int):
        """Set the controller to a given duty, retrying as required."""
        for attempt in range(self.SPI_ATTEMPTS):
            async with self._hardware_lock:
                self.spi_xfer(b"s" + int(val).to_bytes(2, "little"))
                await asyncio.sleep(self.SETTLE_TIME_S)
                resp = self._convert(self.spi_xfer([0] * 2))
            if resp == val:
                if attempt > 1:
                    self._logger.debug(f"Set lamp to {val} after {attempt} attempts.")
                return
            if attempt == 4:
                await self.reset()
            else:
                await asyncio.sleep(self.SETTLE_TIME_S)
        raise SpiControllerError(f"Failed to set lamp to {val}")


class FadeableEndpoint(Endpoint[Fadeable]):
    """An endpoint for a Fadeable."""

    def __init__(self, *args, **kwargs):
        """Initialise a new endpoint at `prefix` for the given fadeable."""
        super().__init__(*args, **kwargs)
        self.router.get("/")(self.get_duty)
        self.router.put("/")(self.set_duty)
        self.router.put("/fade")(self.start_fade)
        self.router.delete("/fade")(self.cancel_fade)

    async def get_duty(self):
        """Get duty."""
        return {"value": await self.thing.get_duty()}

    async def set_duty(
        self, duty: Optional[int] = None, percent_duty: Optional[float] = None
    ):
        """Set duty."""
        if duty is not None:
            await self.thing.set_duty(duty)
        elif percent_duty is not None:
            await self.thing.set_percent_duty(percent_duty)
        else:
            raise ValueError("One of percent_duty or duty must be supplied.")
        return await self.get_duty()

    async def start_fade(
        self,
        duty: Optional[int] = None,
        percent_duty: Optional[float] = None,
        duration: Optional[int] = None,
    ):
        """Start fade."""
        kwargs = dict(duty=duty, percent_duty=percent_duty, duration=duration)
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        asyncio.create_task(self.thing.fade(**kwargs))
        return {"state": "success"}

    async def cancel_fade(self):
        """Cancel fade."""
        self.thing.cancel_fade()
        return {"state", "success"}
