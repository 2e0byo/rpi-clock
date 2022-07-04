import asyncio

from gpiozero import LED

from . import pinmap
from .button import ZeroButton
from .fadeable import PWM, Lamp
from .lcd import Lcd
from .pin import Pin

loop = asyncio.get_event_loop()


backlight = PWM(pinmap.BACKLIGHT_CHANNEL)
lcd = Lcd(backlight=backlight)
# lamp = Lamp(pi)
from unittest.mock import MagicMock

lamp = MagicMock()

volume = PWM(pinmap.VOLUME_CHANNEL)
mute = LED(pinmap.MUTE_PIN, active_high=False)
mute.on()

up_button = ZeroButton(
    pinmap.UP_BUTTON_PIN, suppress=True, name="UpButton", blocking=True
)
down_button = ZeroButton(
    pinmap.DOWN_BUTTON_PIN, suppress=True, name="DownButton", blocking=True
)
enter_button = ZeroButton(
    pinmap.ENTER_BUTTON_PIN, suppress=True, name="EnterButton", blocking=True
)
