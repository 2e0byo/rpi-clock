import asyncio
from time import sleep

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


class Button:
    GLITCH_FILTER_DURATION = 50

    def __init__(self, pin: int, inverted: bool = False):
        self.pin = pin
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_DOWN if inverted else pigpio.PUD_UP)
        pi.set_glitch_filter(pin, self.GLITCH_FILTER_DURATION)
        pi.callback(
            pin, pigpio.RISING_EDGE if inverted else pigpio.FALLING_EDGE, self._callback
        )

    def _callback(self, *args):
        x = self.callback(*args)
        if asyncio.iscoroutine(x):
            asyncio.create_task(x)

    def callback(self, *args):
        print(self.pin, "pressed!")


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
        self.write(self.RESTART)
        self._specials = {}
        self._trans = str.maketrans({})

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
