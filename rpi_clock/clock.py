import asyncio
from datetime import time, timedelta
from logging import getLogger
from pathlib import Path
from time import monotonic, strftime

from .alarm import CachingAlarm
from .hal import down_button, enter_button, lamp, lcd, mute, up_button, volume
from .mopidy import mopidy_volume, play, stop

logger = getLogger(__name__)


old = None


FADE_DURATION = 300
# FADE_DURATION = 10
START_VOLUME = 4 / 50
MAX_VOLUME = 0.15
MAX_SOFTWARE_VOLUME = 0.78


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
        await volume.set_percent_duty(MAX_VOLUME)
        mute.off()
        asyncio.create_task(
            mopidy_volume.fade(percent_duty=MAX_SOFTWARE_VOLUME, duration=30)
        )
        asyncio.create_task(lcd.backlight.fade(percent_duty=1))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(e)


async def end_alarm(button):
    """Stop ringing."""
    lamp.cancel_fade()
    mopidy_volume.cancel_fade()
    asyncio.create_task(lamp.fade(duty=0))
    enter_button["press"] = old
    await mopidy_volume.fade(duty=0)
    mute.on()
    await stop()
    display_alarm()


MIN_BRIGHTNESS = 0.03


async def fade_up_down(button):
    if await lamp.get_duty() > 0:
        delta = -0.005
    else:
        delta = 0.005
        await lamp.set_percent_duty(MIN_BRIGHTNESS)
    while button.state:
        current = await lamp.get_percent_duty()
        print(f"{current:1.2}", end="\r", flush=True)
        await lamp.set_percent_duty(current + delta)
        await asyncio.sleep(0.05)
    if await lamp.get_percent_duty() < MIN_BRIGHTNESS:
        await lamp.set_percent_duty(0)


async def up(*args):
    await lamp.set_percent_duty(await lamp.get_percent_duty() + 0.02)


async def down(*args):
    await lamp.set_percent_duty(await lamp.get_percent_duty() - 0.02)


async def incr():
    while up_button.state:
        await lamp.set_duty(await lamp.get_duty() + 1)
        # await asyncio.sleep(0.1)


# up_button["press"] = up
# up_button["long"] = incr
# down_button["press"] = down


async def toggle_backlight(*args):
    if await lcd.backlight.get_percent_duty():
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


alarm = CachingAlarm(dbfile=Path("~/alarm.json").expanduser())
alarm.callback = ring
alarm.adjust_alarm = lambda val: (val - timedelta(seconds=FADE_DURATION))


def display_alarm():
    lcd[1] = "alarm {}: {}".format(
        "Off" if alarm.state == alarm.OFF else "On",
        alarm.target.strftime("%H:%M"),
    )


if not alarm.target:
    alarm.target = time(hour=8, minute=0)
loop = asyncio.get_event_loop()
loop.create_task(clock_loop())
display_alarm()
