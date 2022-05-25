import asyncio
from functools import partial

import pigpio

from .button import PiButton
from .fadeable import PWM, Lamp
from .lcd import Lcd
from .pin import Pin

loop = asyncio.get_event_loop()
pi = pigpio.pi()

BACKLIGHT_PIN = 6
VOLUME_PIN = 26
MUTE_PIN = 14

UP_BUTTON = 16
ENTER_BUTTON = 20
DOWN_BUTTON = 21

backlight = PWM(BACKLIGHT_PIN, pi)
lcd = Lcd(backlight=backlight)
lamp = Lamp(pi)

volume = PWM(VOLUME_PIN, pi)
mute = Pin(pi, MUTE_PIN, Pin.OUT, inverted=True)
mute(True)

up_button = PiButton(pi, UP_BUTTON, suppress=True, name="UpButton")
down_button = PiButton(pi, DOWN_BUTTON, suppress=True, name="DownButton")
enter_button = PiButton(pi, ENTER_BUTTON, suppress=True, name="EnterButton")
