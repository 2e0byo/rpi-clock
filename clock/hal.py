from .hardware import PWM, Button, Lamp, Lcd, LightSensor, Pin

BACKLIGHT_PIN = 6
VOLUME_PIN = 26
MUTE_PIN = 14

UP_BUTTON = 16
ENTER_BUTTON = 20
DOWN_BUTTON = 21

lamp = Lamp()


backlight = PWM(BACKLIGHT_PIN)
lcd = Lcd(backlight=backlight)

volume = PWM(VOLUME_PIN)
mute = Pin(MUTE_PIN, Pin.OUT, True)
mute(True)

up_button = Button(UP_BUTTON)
down_button = Button(DOWN_BUTTON)
enter_button = Button(ENTER_BUTTON)

light_sensor = LightSensor()

backlight.percent_duty = 1
