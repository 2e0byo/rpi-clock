import asyncio

import pigpio

PI = pigpio.pi()

BACKLIGHT_PIN = 6
VOLUME_PIN = 26
MUTE_PIN = 14

DOWN_BUTTON = 16
UP_BUTTON = 20
ENTER_BUTTON = 21


class PWM:
    def __init__(self, pin):
        self.pin = pin
        PI.set_mode(self.pin, 1)
        PI.set_PWM_frequency(self.pin, 10000)  # as high as possible
        PI.set_PWM_range(self.pin, 50)
        # PI.set_PWM_range(self.pin, duty)
        self.duty = 0
        self.fade_delay = 0.01

    @property
    def duty(self):
        return PI.get_PWM_dutycycle(self.pin)

    @duty.setter
    def duty(self, val: int):
        PI.set_PWM_dutycycle(self.pin, val)

    async def fade(self, val: int, duration: int = 0):
        current = self.duty
        step = 1 if current < val else -1
        delay = duration / abs(current - val) if duration else self.fade_delay
        for br in range(current, val + step, step):
            self.duty = br
            await asyncio.sleep(delay)


class PinError(Exception):
    pass


class Pin:
    OUT = 0
    IN = 1

    def __init__(self, pin: int, mode: int, inverted: bool = False):
        self.pin = pin
        self.mode = mode
        self.inverted = inverted
        PI.set_mode(pin, mode)

    def __call__(self, val=None):
        if val == None:
            val = PI.read(self.pin)
            return val if not self.inverted else not val

        if self.mode != self.OUT:
            raise PinError("Pin not in out mode")
        PI.write(self.pin, val if not self.inverted else not val)

    def on(self):
        self.__call__(1)

    def off(self):
        self.__call__(0)


class Button:
    GLITCH_FILTER_DURATION = 100

    def __init__(self, pin: int, inverted: bool = False):
        self.pin = pin
        PI.set_mode(pin, pigpio.INPUT)
        PI.set_pull_up_down(pin, pigpio.PUD_DOWN if inverted else pigpio.PUD_UP)
        PI.set_glitch_filter(pin, self.GLITCH_FILTER_DURATION)
        PI.callback(
            pin, pigpio.RISING_EDGE if inverted else pigpio.FALLING_EDGE, self.callback
        )

    def callback(self, *args):
        print(self.pin, "pressed!")


backlight = PWM(BACKLIGHT_PIN)

volume = PWM(VOLUME_PIN)
mute = Pin(MUTE_PIN, Pin.OUT, True)

up_button = Button(UP_BUTTON)
down_button = Button(DOWN_BUTTON)
enter_button = Button(ENTER_BUTTON)

backlight.duty = 50

# Define some constants from the datasheet
DEVICE = 0x23  # Default device I2C address
POWER_DOWN = 0x00  # No active state
POWER_ON = 0x01  # Power on
RESET = 0x07  # Reset data register value
ONE_TIME_HIGH_RES_MODE = 0x20

i2c = PI.i2c_open(2, DEVICE)


def convertToNumber(data):
    return (data[1] + (256 * data[0])) / 1.2


def readLight(addr=DEVICE):
    data = PI.i2c_read_block_data(i2c, ONE_TIME_HIGH_RES_MODE)
    return convertToNumber(data)
