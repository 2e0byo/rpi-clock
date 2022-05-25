import asyncio
import logging
from collections import UserDict

import pigpio

from .timer import Timer


class Button(UserDict):
    """A button, api loosely inspired by Peter Hinch's micropython `Pushbutton`.

    This class assumes its `.callback()` will be called from elsewhere.  It mostly exists for testing."""

    HOOKS = {"press", "release", "long", "double"}
    FALLING_EDGE = 0
    RISING_EDGE = 1
    instances = []

    def __init__(
        self,
        inverted: bool = False,
        long_ms: int = 1_000,
        double_ms: int = 400,
        suppress: bool = False,
        name: str = None,
    ):
        self._event = asyncio.Event()
        self._edge: int = None
        self.rising_edge = self.RISING_EDGE
        self.falling_edge = self.FALLING_EDGE
        if inverted:
            self.rising_edge, self.falling_edge = self.falling_edge, self.rising_edge
        self.inverted = inverted
        self.data = {k: None for k in self.HOOKS}

        self._double_ms = double_ms
        self._long_ms = long_ms
        self.suppress = suppress
        self._loop = asyncio.get_event_loop()
        self._long_timer = Timer(long_ms)
        self._double_timer = Timer(double_ms, self._doubleclick_timeout)
        self._double_pending = False
        self._double_ran = False
        self.state = False
        self._loop.create_task(self._button_check_loop())
        self.name = name or f"Button-{len(self.instances)}"
        self.instances.append(self.name)
        self._logger = logging.getLogger(name)

    async def _doubleclick_timeout(self):
        """In suppress mode, work out if a double click has expired, and if so,
        call the release fn if it exists."""

        self._double_pending = False
        if not self.suppress:
            return

        if not self.data["release"]:
            return

        if (
            self.state
            and not self.data["long"]
            or self.data["long"]
            and not self._long_timer.running
        ):
            asyncio.create_task(self.call(self.data["release"]))

    @property
    def double_ms(self):
        return self._double_ms

    @double_ms.setter
    def double_ms(self, val: int):
        self._double_ms = val
        self._double_timer.duration = val

    @property
    def long_ms(self):
        return self._long_ms

    @long_ms.setter
    def long_ms(self, val: int):
        self._long_ms = val
        self._long_timer.duration = val

    def _callback(self, gpio: int, level: int, tick: int):
        """
        Callback for button events.

        Note that this runs in a different thread context from the main event
        loop.
        """
        self._edge = level
        self._loop.call_soon_threadsafe(lambda: self._event.set())

    async def call(self, fn):
        x = fn(self)
        if asyncio.iscoroutine(x):
            x = await x
        return x

    async def _button_check_loop(self):
        """Respond to events from the callback."""
        while True:
            await self._event.wait()
            edge = self._edge
            self._event.clear()
            if edge == self.falling_edge:
                self._logger.debug("Got falling edge.")
                self.state = True
                if self.data["press"]:
                    asyncio.create_task(self.call(self.data["press"]))

                if self.data["long"]:
                    self._long_timer.trigger()

                if self.data["double"]:
                    if self._double_timer.running:
                        self._double_timer.cancel()
                        self._double_pending = False
                        self._double_ran = True
                        asyncio.create_task(self.call(self.data["double"]))
                    else:
                        self._double_timer.trigger()
                        await asyncio.sleep(0)
                        self._double_pending = True

            elif edge == self.rising_edge:
                self._logger.debug("Got rising edge.")
                self.state = False
                if self.data["release"]:
                    if self.suppress:
                        if (
                            not self._double_pending
                            and not self._double_ran
                            and (
                                not self.data["long"]
                                or (self.data["long"] and self._long_timer.running)
                            )
                        ):
                            asyncio.create_task(self.call(self.data["release"]))
                    else:
                        asyncio.create_task(self.call(self.data["release"]))

                    self._long_timer.cancel()
                    self._double_ran = False

            else:
                raise ValueError(f"Unknown edge {edge} received.")

    def __setitem__(self, key: str, fn: callable = None):
        """Set a function to run."""
        if key not in self.HOOKS:
            raise ValueError(f"Function {key} is not a valid hook")
        self.data[key] = fn
        if key == "long":
            self._long_timer.fn = fn

    def __getitem__(self, key: str):
        return self.data[key]

    def __delitem__(self, key: str):
        self.data[key] = None


class PiButton(Button):
    def __init__(
        self,
        pi,
        pin,
        *args,
        inverted=False,
        debounce_ms: int = 100,
        **kwargs,
    ):
        kwargs["inverted"] = inverted
        super().__init__(*args, **kwargs)
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_DOWN if inverted else pigpio.PUD_UP)
        pi.set_glitch_filter(pin, debounce_ms)
        pi.callback(pin, pigpio.EITHER_EDGE, self._callback)
