"""Hardware mapping for the device.

We define this here, rather than inside `hal.py` to simplify using it in other
tools.
"""
# TODO make this a config file or env vars

BACKLIGHT_PIN = 13
VOLUME_PIN = 12

BACKLIGHT_CHANNEL = 1
VOLUME_CHANNEL = 0


MUTE_PIN = 14
UP_BUTTON_PIN = 16
ENTER_BUTTON_PIN = 20
DOWN_BUTTON_PIN = 6
