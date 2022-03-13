import asyncio
from collections import deque
from functools import partial
from time import monotonic, sleep

import pigpio
from smbus import SMBus

pi = pigpio.pi()


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

    @property
    def percent_duty(self):
        return self.duty / self.max_duty

    @percent_duty.setter
    def percent_duty(self, val):
        if val < 0:
            self.duty = 0
        elif val > 1:
            self.max_duty
        else:
            self.duty = round(val * self.max_duty)


class PWM(Fadeable):
    """A fadeable pwm output."""

    MAX_DUTY = 50
    FREQ = 10000

    def __init__(self, pin, *args, freq: int = None, max_duty: int = None, **kwargs):
        self.pin = pin
        self.max_duty = max_duty or self.MAX_DUTY
        pi.set_mode(self.pin, 1)
        pi.set_PWM_frequency(self.pin, freq or self.FREQ)
        pi.set_PWM_range(self.pin, self.max_duty)
        super().__init__(*args, **kwargs)

    @property
    def duty(self):
        return pi.get_PWM_dutycycle(self.pin)

    @duty.setter
    def duty(self, val: int):
        pi.set_PWM_dutycycle(self.pin, val)


class Lamp(Fadeable):
    """An SPI controlled lamp."""

    MOSI = 10
    MISO = 9
    SCLK = 11
    CS = 8
    BAUD = 10000
    MODE = 1

    def __init__(
        self,
        *args,
        cs: int = None,
        miso: int = None,
        mosi: int = None,
        sclk: int = None,
        baud: int = None,
        mode: int = None,
        **kwargs,
    ):
        self.cs = cs or self.CS
        pi.bb_spi_open(
            self.cs,
            miso or self.MISO,
            mosi or self.MOSI,
            sclk or self.SCLK,
            baud or self.BAUD,
            mode or self.MODE,
        )
        self.max_duty = 1023

        super().__init__(*args, **kwargs)

    @property
    def duty(self):
        pi.bb_spi_xfer(self.cs, b"r")
        sleep(0.001)
        return int.from_bytes(pi.bb_spi_xfer(self.cs, [0] * 2)[1], "little")

    @duty.setter
    def duty(self, br: int):
        br = int(br).to_bytes(2, "little")
        pi.bb_spi_xfer(self.cs, b"s" + br)
        sleep(0.001)
        resp = pi.bb_spi_xfer(self.cs, [0] * 2)[1]

    def __del__(self):
        try:
            pi.bb_spi_close(self.cs)
        except Exception:
            pass


class LightSensor:
    """An ambient light sensor, reading in lux."""

    ADDRESS = 0x23
    POWER_DOWN = 0x00
    POWER_ON = 0x01
    RESET = 0x07
    ONE_TIME_HIGH_RES_MODE = 0x20
    CONTINUOUS_HIGH_RES_MODE = 0b0001_0000

    def __init__(self, addr: int = None):
        self.bus = SMBus(1)
        self.addr = addr or self.ADDRESS
        self.val = None

    def read(self):
        data = self.bus.read_i2c_block_data(self.addr, self.ONE_TIME_HIGH_RES_MODE)
        self.val = self.convert(data)
        return self.val

    def convert(self, data):
        return (data[1] + (256 * data[0])) / 1.2


class PinError(Exception):
    pass


class Pin:
    OUT = 0
    IN = 1

    def __init__(self, pin: int, mode: int, inverted: bool = False):
        self.pin = pin
        self.mode = mode
        self.inverted = inverted
        pi.set_mode(pin, mode)

    def __call__(self, val=None):
        if val == None:
            val = pi.read(self.pin)
            return val if not self.inverted else not val

        if self.mode != self.OUT:
            raise PinError("Pin not in out mode")
        pi.write(self.pin, val if not self.inverted else not val)

    def on(self):
        self.__call__(1)

    def off(self):
        self.__call__(0)


class Timer:
    """Asyncio timer, api based loosely on Peter Hinch's timer."""

    def __init__(self):
        self.task = None
        self.loop = asyncio.get_event_loop()

    def trigger(self, duration_ms: int, fn: callable):
        self.fn = fn
        self.cancel()
        self.task = asyncio.run_coroutine_threadsafe(
            self._trigger(duration_ms), self.loop
        )

    def cancel(self):
        try:
            self.task.cancel()
        except Exception:
            pass

    async def _call(self):
        print("calling", self.fn)
        x = self.fn()
        print("got", x)
        if asyncio.iscoroutine(x):
            print("awaiting")
            await x
            print("done")

    async def _trigger(self, duration_ms):
        print("sleeping")
        await asyncio.sleep(duration_ms / 1_000)
        print("running")
        await self._call()


class Button:
    """A button, api loosely inspired by Peter Hinch's micropython `Pushbutton`."""

    GLITCH_FILTER_DURATION = 50
    HOOKS = {"press", "release", "long", "double"}
    FALLING_EDGE = 0
    RISING_EDGE = 1
    WDT = 2

    def __init__(
        self,
        pin: int,
        inverted: bool = False,
        debounce_ms: int = 100,
        long_ms: int = 1_000,
        double_click_ms: int = 400,
        suppress: bool = False,
    ):
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_DOWN if inverted else pigpio.PUD_UP)
        pi.set_glitch_filter(pin, debounce_ms)
        pi.callback(pin, pigpio.EITHER_EDGE, self._callback)
        self.pin = pin
        self.in_progress = False
        self.hooks = {k: None for k in self.HOOKS}
        self.blocked = False
        self.double_click_ms = double_click_ms
        self.long_ms = long_ms
        self.suppress = suppress
        self._last = deque([], 2)
        self.state = False
        self._double_click_timer = Timer()
        self._long_timer = Timer()
        self.loop = asyncio.get_event_loop()

    async def _wrapper(self, future):
        await future
        print("unblocked")
        self.blocked = False

    def _call(self, fn: callable, *args):
        """Call or run a fn or coro."""
        print("blocked")
        self.blocked = True
        x = fn(*args)
        if asyncio.iscoroutine(x):
            asyncio.run_coroutine_threadsafe(self._wrapper(x), self.loop)
        else:
            print("unblocked")
            self.blocked = False

    def _callback(self, gpio: int, level: int, tick: int):
        print(gpio, "rising" if level == self.RISING_EDGE else "falling")
        if self.blocked:
            return

        fn = {
            self.RISING_EDGE: self.hooks["release"],
            self.FALLING_EDGE: self._push,
            self.WDT: self._timeout,
        }[level]
        if fn:
            fn()

    def _timeout(self):
        if self.state and self.hooks["long"]:
            self._call(self.hooks["long"])

    def _release_if_not_doubled(self):
        if self.hooks["double"] and (
            now - self._last[-1] > self.double_click_ms / 1_000
        ):
            self._call(self.hooks["release"])

    def _release(self):
        self.state = False
        now = monotonic()
        if suppress:
            if self.hooks["double"] and (
                now - self._last[-1] < self.double_click_ms / 1_000
            ):
                # double press has been called
                return
            if self.hooks["double"]:
                # trigger when timer elapses if we haven't double pressed in that time.
                self._double_click_timer.trigger(
                    self.double_click_ms, self._release_if_not_doubled
                )
                return
            if self.hooks["long"] and diff > self.long_ms:
                # long has been called
                return

        if self.hooks["release"]:
            self._call(self.hooks["release"])

    def _long(self):
        if self.state and self.hooks["long"]:
            self._call(self.hooks["long"])

    def _push(self):
        self.state = True
        now = monotonic()
        if self.hooks["press"]:
            self._call(self.hooks["press"])
        if (
            self.hooks["double"]
            and self._last
            and (now - self._last <= self.double_click_ms / 1_000)
        ):
            self._call(self.hooks["double"])
        if self.hooks["long"]:
            self._long_timer.trigger(self.long_ms, self._long)
        self._last.append(now)

    def __setitem__(self, key: str, val: callable = None):
        """Set a function to run."""
        if key not in self.HOOKS:
            raise Exception(f"Function {key} is not a valid hook")
        self.hooks[key] = val

    def __getitem__(self, key: str):
        return self.hooks[key]


class Lcd:
    BACKSPACE = "\b"
    CLEAR = "\f"
    HOME = "\x1b[H"
    BLINK = "\x1b[LB"
    GOTOX = "\x1b[Lx"
    GOTOY = "\x1b[Ly"
    GOTO = "\x1b[Lx{:03}y{:03};"
    RESTART = "\x1b[LI"
    NEWCHAR = "\x1b[LG{}{:016};"
    CURSOR = "\x1b[LC"
    NOCURSOR = "\x1b[Lc"

    def __init__(
        self,
        lines: int = 2,
        cols: int = 16,
        path: str = "/dev/lcd",
        backlight: Fadeable = None,
    ):
        self.path = path
        self.lines = lines
        self.cols = cols
        self.backlight = backlight
        self._buffer = [""] * lines
        self._specials = {}
        self._trans = str.maketrans({})
        self.write(self.RESTART)
        self.write(self.NOCURSOR)

    def goto(self, x: int, y: int):
        self.write(self.GOTO.format(x, y))

    def write(self, s: str):
        with open(self.path, "w") as f:
            f.write(s)

    def newchar(self, alias: str, char: bytearray):
        index = len(self.specials.keys()) + 1 % 7
        self.write(self.NEWCHAR.format(keys, "".join(hex(b)[2:] for b in char)))
        self._specials[alias] = index.to_bytes(1, "big")
        self._trans = str.maketrans(self._specials)

    def __setitem__(self, line: int, msg: str):
        msg = f"{msg:{self.cols}.{self.cols}}"
        if self._buffer[line] != msg:
            self._buffer[line] = msg
            self.goto(0, line)
            self.write(msg.translate(self._trans))

    def __del__(self):
        if self.backlight:
            del self.backlight
