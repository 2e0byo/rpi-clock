from gpiozero import LED

from . import pinmap
from .button import ZeroButton
from .fadeable import PWM, Lamp
from .lcd import Lcd

backlight = PWM(pinmap.BACKLIGHT_CHANNEL, name="backlight")
lcd = Lcd(backlight=backlight)
lamp = Lamp(name="lamp")

volume = PWM(pinmap.VOLUME_CHANNEL, name="backlight")
mute = LED(pinmap.MUTE_PIN, active_high=False)

up_button = ZeroButton(
    pinmap.UP_BUTTON_PIN, suppress=True, name="UpButton", blocking=True
)
down_button = ZeroButton(
    pinmap.DOWN_BUTTON_PIN, suppress=True, name="DownButton", blocking=True
)
enter_button = ZeroButton(
    pinmap.ENTER_BUTTON_PIN, suppress=True, name="EnterButton", blocking=True
)
