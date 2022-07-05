import asyncio
import logging
from abc import ABC, abstractmethod
from time import monotonic, sleep

from gpiozero import SPI, Device
from gpiozero.exc import SPIFixedRate
from gpiozero.pins import Factory
from rpi_hardware_pwm import HardwarePWM


class Fadeable(ABC):
    """Base Class for a fadeable output."""

    instances = []
    MAX_FADE_FREQ_HZ = 90  # no point updating faster than this.

    def __init__(self, *args, **kwargs):
        """Initialise a new fadeable object."""
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
        """Fade from current state in a given time."""
        self.cancel_fade()
        self._fade_task = asyncio.create_task(self._fade(duty, percent_duty, duration))
        await self._fade_task
        self._fade_task = None

    def cancel_fade(self):
        """Cancel a running fade."""
        if self._fade_task:
            self._fade_task.cancel()

    async def set_duty(self, val: int):
        """
        Set duty asynchronously.

        Descendents *may* override this method to provide error handling or
        yield during long asynchronous processes.
        """
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
        """Get current duty as a percentage."""
        return self.duty / self.max_duty

    @percent_duty.setter
    def percent_duty(self, val: float):
        """Set current duty as a percentage."""
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
        """Get current duty."""
        pass  # pragma: no cover


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

    @property
    def duty(self):
        """Get the current raw duty cycle."""
        return self.pwm._duty_cycle

    @duty.setter
    def duty(self, val: int):
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
        self._duty = None
        try:
            self.duty = 0
        except SpiControllerError:
            self._reset()
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

    @property
    def duty(self):
        """Get the current duty."""
        return self._duty

    def get_hardware_duty(self):
        """Get the current duty directly from the controller."""
        self.spi_xfer(b"r")
        sleep(self.SETTLE_TIME_S)
        return self._convert(self.spi_xfer([0] * 2))

    @duty.setter
    def duty(self, val: int):
        duty = int(val).to_bytes(2, "little")
        self.spi_xfer(b"s" + duty)
        sleep(self.SETTLE_TIME_S)
        resp = self._convert(self.spi_xfer([0] * 2))
        if resp != val:
            raise SpiControllerError(f"Failed to set lamp to {val}")
        self._duty = val

    async def reset(self):
        """Reset the controller."""
        self._logger.debug("Resetting")
        self.cs.state = 0
        await asyncio.sleep(3)
        self.cs.state = 1

    def _reset(self):
        self.cs.state = 0
        sleep(3)
        self.cs.state = 1

    async def set_duty(self, val: int):
        """Set the controller to a given duty, retrying as required."""
        for attempt in range(self.SPI_ATTEMPTS):
            try:
                self.duty = val
                if attempt > 1:
                    self._logger.debug(f"Set lamp to {val} after {attempt} attempts.")
                return
            except SpiControllerError:
                if attempt == 4:
                    await self.reset()
                else:
                    await asyncio.sleep(
                        0.3 * attempt
                    )  # backing off is enough most of the time.

        raise SpiControllerError(f"Failed to set lamp to {val}")
