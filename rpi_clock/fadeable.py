import asyncio
from abc import ABC, abstractmethod
from json import dump, load
from pathlib import Path
from time import monotonic, sleep
from typing import Optional, cast
from unittest.mock import AsyncMock

from gpiozero import SPI, Device
from gpiozero.exc import SPIFixedRate
from gpiozero.pins import Factory
from gpiozero.pins.native import NativeFactory
from rpi_hardware_pwm import HardwarePWM
from structlog import get_logger
from xdg_base_dirs import xdg_cache_home

from .endpoint import Endpoint

logger = get_logger()


class Fadeable(ABC):
    """Base Class for a fadeable output."""

    instances = []
    max_duty: int

    def __init__(
        self,
        *,
        max_fade_freq_hz: int = 50,
        name: Optional[str] = None,
        max_duty: int = 100,
    ):
        """Initialise a new fadeable object."""
        name = name or f"{__name__}-{len(self.instances)}"
        self.name = name
        self.instances.append(name)
        self._logger = logger.bind(name=name)
        self.max_fade_freq_hz = max_fade_freq_hz
        self._fade_task = None
        self._duty = 0
        self._zero_task = asyncio.get_event_loop().create_task(self._zero())
        self._fade_lock = asyncio.Lock()
        self._max_duty = max_duty
        self.max_duty = max_duty
        self.min_duty = 0

    def set_max_duty(self, duty: Optional[int]):
        if duty is None:
            self.max_duty = self._max_duty
        else:
            self.max_duty = max(min(duty, self._max_duty), 0)

    def set_min_duty(self, duty: Optional[int]):
        if duty is None:
            self.min_duty = 0
        else:
            self.min_duty = min(max(duty, 0), self.max_duty)

    async def fade(
        self,
        *,
        duty: int | None = None,
        percent_duty: float | None = None,
        duration: float = 1,
    ):
        """Fade from current state in a given time."""
        if duty is None and percent_duty is None:
            raise ValueError("One of percent_duty or duty must be supplied.")
        if duty is None:
            duty = self._convert_duty(cast(float, percent_duty))

        async with self._fade_lock:
            self.cancel_fade()
            self._fade_task = asyncio.create_task(self._fade(duty, duration))
            await self._fade_task
            self._fade_task = None

    def cancel_fade(self):
        """Cancel a running fade.

        Not guaranteed to succeed immediately.
        """
        if self._fade_task:
            self._fade_task.cancel()

    async def _zero(self):
        self._logger.info("Zeroing")
        await self.set_duty(0)

    def _ceil(self, duty) -> int:
        return min(self.max_duty, duty)

    def _constrain(self, duty) -> int:
        return max(self._ceil(duty), self.min_duty)

    async def set_duty(self, val: int):
        """Set duty."""
        # only floor to 0 to allow turning off.
        val = max(self._ceil(val), 0)
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

    async def _fade(self, duty: int, duration: float):
        constrained_duty = self._constrain(duty)
        current = await self.get_duty()
        if constrained_duty == current:
            return
        step = 1 if current < constrained_duty else -1
        steps = abs(current - constrained_duty)
        freq = steps / duration
        while freq > self.max_fade_freq_hz:
            steps //= 2
            step *= 2
            freq = steps / duration

        delay = 1 / freq

        for br in range(current, constrained_duty + step, step):
            start = monotonic()
            br = max(br, 0)
            br = min(br, self.max_duty)
            await self.set_duty(br)
            elapsed = monotonic() - start
            await asyncio.sleep(max(0, delay - elapsed))
        # duty may be less than min duty; permit turning off.
        await self.set_duty(duty)

    async def get_percent_duty(self) -> float:
        """Get current duty as a percentage."""
        return await self.get_duty() / (self.max_duty - self.min_duty)

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
            return round(val * (self.max_duty - self.min_duty)) + self.min_duty


class MockFadeable(Fadeable):
    """A fadeable with the output mocked."""

    def __init__(self, *args, **kwargs):
        """Initialise a new MockFadeable."""
        self.set_duty_mock = AsyncMock()
        self.get_duty_mock = AsyncMock()
        # Generally when mocking we don't want anything funny happening with fading.
        kwargs["max_fade_freq_hz"] = kwargs.get("max_fade_freq_hz", 1_000_000_000)
        kwargs["max_duty"] = kwargs.get("max_duty", 100)
        super().__init__(*args, **kwargs)
        self.set_duty_mock = AsyncMock()  # replace as set_duty called in `__init__()`.

    async def set_hardware_duty(self, val: int):
        """Set the mocked duty and call the mock."""
        await self.set_duty_mock(val)
        self.get_duty_mock.return_value = val

    async def get_hardware_duty(self) -> int:
        """Get the mocked duty and call the mock."""
        return await self.get_duty_mock()


def default_cache_dir() -> Path:
    return xdg_cache_home() / "rpi_clock"


class CachingFadeable(Fadeable):
    """A fadeable which caches runtime-settable values between runs if possible."""

    def __init__(self, *args, cache_dir: Path | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        cache_dir = cache_dir or default_cache_dir()
        cache_dir.mkdir(exist_ok=True, parents=True)
        self.cachef = cache_dir / f"{self.name}.json"
        cache = self.load_cache()

        for key in {"min_duty", "max_duty"}:
            try:
                getattr(self, f"set_{key}")(cache[key])
            except Exception:
                self._logger.exception("Failed to set %s", key)

    def load_cache(self) -> dict:
        try:
            with self.cachef.open() as f:
                return load(f)
        except Exception:
            self._logger.exception("Failed to load cache")
            return {}

    def save_cache(self, cache: dict):
        with self.cachef.open("w") as f:
            dump(cache, f)

    def set_cache(self, key, val):
        cache = self.load_cache()
        cache[key] = val
        self.save_cache(cache)

    def set_max_duty(self, *args, **kwargs):
        super().set_max_duty(*args, **kwargs)
        self.set_cache("max_duty", self.max_duty)

    def set_min_duty(self, *args, **kwargs):
        super().set_min_duty(*args, **kwargs)
        self.set_cache("min_duty", self.min_duty)


class PWM(CachingFadeable):
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


class Lamp(CachingFadeable):
    """An SPI controlled lamp."""

    SETTLE_TIME_S = 0.009
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
        pin_factory: Factory | None = None,
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
        self.cs = NativeFactory().pin(cs)
        self.cs.function = "output"
        self.cs.state = 1
        kwargs["max_duty"] = kwargs.get("max_duty", 1023)
        self._hardware_lock = asyncio.Lock()
        super().__init__(*args, **kwargs)
        if rate_error:
            self._logger.error(rate_error)

    def spi_cmd(self, data: bytes) -> bytes:
        """Transfer data to and from the controller over spi.

        This method abstracts from a particular spi driver.
        """
        return bytes(self.spi.transfer(data + b"#")[:-1])

    async def get_duty(self):
        """Get the current duty."""
        return self._duty

    async def get_hardware_duty(self):
        """Get the current duty directly from the controller."""
        async with self._hardware_lock:
            self.spi_cmd(b"r")
            sleep(self.SETTLE_TIME_S)
            return int(self.spi_cmd(b" " * 4))

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
                self.spi_cmd(f"s{val}".encode())
                await asyncio.sleep(self.SETTLE_TIME_S)
                raw = self.spi_cmd(b" " * 4)
                try:
                    resp = int(raw)
                    if resp != val:
                        self._logger.debug(f"Got {resp} for {val} ({bytes(raw)})")
                    if resp == val:
                        if attempt > 1:
                            self._logger.debug(
                                f"Set lamp to {val} after {attempt} attempts."
                            )
                        return
                    if attempt == 4:
                        await self.reset()
                    else:
                        await asyncio.sleep(self.SETTLE_TIME_S)
                except ValueError:
                    await self.reset()
        raise SpiControllerError(f"Failed to set lamp to {val}")


class FadeableEndpoint(Endpoint[CachingFadeable]):
    """An endpoint for a Fadeable."""

    def __init__(self, *args, **kwargs):
        """Initialise a new endpoint at `prefix` for the given fadeable."""
        super().__init__(*args, **kwargs)
        self.router.get("/")(self.get_duty)
        self.router.put("/")(self.set_duty)
        self.router.get("/raw-duty")(self.get_raw_duty)
        self.router.put("/fade")(self.start_fade)
        self.router.delete("/fade")(self.cancel_fade)
        self.router.get("/min-duty")(self.get_min_duty)
        self.router.put("/min-duty")(self.set_min_duty)
        self.router.delete("/min-duty")(lambda: self.thing.set_min_duty(None))
        self.router.get("/max-duty")(self.get_max_duty)
        self.router.put("/max-duty")(self.set_max_duty)
        self.router.delete("/max-duty")(lambda: self.thing.set_max_duty(None))

    def get_min_duty(self):
        """Get min duty."""
        return {"value": self.thing.min_duty}

    def set_min_duty(self, duty: int):
        """Set min duty."""
        self.thing.set_min_duty(duty)
        return self.get_min_duty()

    def get_max_duty(self):
        """Get max duty."""
        return {"value": self.thing.max_duty}

    def set_max_duty(self, duty: int):
        """Set max duty."""
        self.thing.set_max_duty(duty)
        return self.get_max_duty()

    async def get_duty(self):
        """Get duty."""
        return {"value": await self.thing.get_percent_duty()}

    async def set_duty(self, duty: float):
        """Set duty."""
        await self.thing.set_percent_duty(duty)
        return await self.get_duty()

    async def get_raw_duty(self):
        """Get raw duty."""
        return {"value": await self.thing.get_duty()}

    async def start_fade(
        self,
        duty: float,
        duration: Optional[float] = None,
    ):
        """Start fade."""
        kwargs = dict(percent_duty=duty, duration=duration)
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        asyncio.create_task(self.thing.fade(**kwargs))
        return {"state": "success"}

    async def cancel_fade(self):
        """Cancel fade."""
        self.thing.cancel_fade()
        return {"state": "success"}
