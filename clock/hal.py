from .hardware import Lamp, PWM, LightSensor, Button, Pin, Lcd

BACKLIGHT_PIN = 6
VOLUME_PIN = 26
MUTE_PIN = 14

DOWN_BUTTON = 16
UP_BUTTON = 20
ENTER_BUTTON = 21

lamp = Lamp()


backlight = PWM(BACKLIGHT_PIN)
lcd = Lcd(backlight=backlight)

volume = PWM(VOLUME_PIN)
mute = Pin(MUTE_PIN, Pin.OUT, True)

up_button = Button(UP_BUTTON)
down_button = Button(DOWN_BUTTON)
enter_button = Button(ENTER_BUTTON)

light_sensor = LightSensor()

backlight.percent_duty = 1
