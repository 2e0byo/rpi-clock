from clock.hal import backlight
from clock.hardware import Fadeable


if __name__ == "__main__":

    l = Lcd(backlight=backlight)
    l.backlight.percent_duty = 0.5

    l[0] = "line 12"
    l[1] = "line 2"

    del l
