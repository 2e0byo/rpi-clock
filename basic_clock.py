import asyncio
from datetime import datetime, time, timedelta
from logging import getLogger
from time import monotonic, strftime

from rpi_clock import run
from rpi_clock.alarm import Alarm
from rpi_clock.hal import down_button, enter_button, lamp, lcd, mute, up_button, volume
from rpi_clock.mopidy import play, stop

logger = getLogger(__name__)


old = None


async def end_alarm(button):
    """Stop ringing."""
    await stop()
    logger.debug("fade off lamp")
    asyncio.create_task(lamp.fade(duty=0))
    logger.debug("restore button")
    enter_button["press"] = old
    logger.debug("fade off volume")
    await volume.fade(duty=0, duration=3)
    mute.on()
    display_alarm()


FADE_DURATION = 300
# FADE_DURATION = 10
START_VOLUME = 4 / 50
MAX_VOLUME = 11 / 50


async def ring():
    """Ring."""
    global old
    old = enter_button["press"]
    enter_button["press"] = end_alarm
    logger.debug("ring ring")
    lcd[1] = "ring ring"
    try:
        await lamp.fade(duty=500, duration=FADE_DURATION)
        await play()
        mute.off()
        volume.percent_duty = START_VOLUME
        asyncio.create_task(volume.fade(percent_duty=MAX_VOLUME, duration=30))
        asyncio.create_task(lcd.backlight.fade(percent_duty=1))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(e)


MIN_BRIGHTNESS = 0.03


async def fade_up_down(button):
    if lamp.duty > 0:
        delta = -0.005
    else:
        delta = 0.005
        lamp.percent_duty = MIN_BRIGHTNESS
    while button.state:
        print(f"{lamp.percent_duty:1.2}", end="\r", flush=True)
        duty = lamp._convert_duty(lamp.percent_duty + delta)
        await lamp.set_duty(duty)
        await asyncio.sleep(0.05)
    if lamp.percent_duty < MIN_BRIGHTNESS:
        lamp.percent_duty = 0


def up(*args):
    lamp.percent_duty += 0.02


def down(*args):
    lamp.percent_duty -= 0.02


async def incr():
    while up_button.state:
        lamp.duty += 1
        # await asyncio.sleep(0.1)


# up_button["press"] = up
# up_button["long"] = incr
# down_button["press"] = down


async def toggle_backlight(*args):
    if lcd.backlight.percent_duty:
        await lcd.backlight.fade(percent_duty=0)
    else:
        await lcd.backlight.fade(percent_duty=1)


# enter_button["press"] = toggle_backlight
up_button["press"] = toggle_backlight
down_button["press"] = toggle_backlight
enter_button["long"] = fade_up_down
enter_button["release"] = toggle_backlight


async def clock_loop():
    while True:
        start = monotonic()
        lcd[0] = "{:^16}".format(strftime("%H:%M:%S"))
        delay = 1 + start - monotonic()
        await asyncio.sleep(delay)


alarm = Alarm(callback=ring)


def display_alarm():
    lcd[1] = "alarm {}: {}".format(
        "Off" if alarm.state == alarm.OFF else "On",
        alarm.target.strftime("%H:%M"),
    )


alarm._target.callback = display_alarm
alarm._state.callback = display_alarm
alarm.target = time(hour=8, minute=0)
display_alarm()


loop = asyncio.get_event_loop()
loop.create_task(clock_loop())
loop.run_forever()
