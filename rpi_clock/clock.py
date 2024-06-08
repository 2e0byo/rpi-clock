import asyncio
from datetime import time, timedelta
from pathlib import Path
from time import monotonic, strftime

from structlog import get_logger

from .alarm import CachingAlarm
from .display import LcdDisplay, Menu, MenuItem
from .hal import down_button, enter_button, lamp, lcd, mute, up_button, volume
from .mopidy import mopidy_volume, play, stop
from .reactive import Watched

logger = get_logger()


old = None


FADE_DURATION = 300
START_VOLUME = 4 / 50
MAX_VOLUME = 0.15
MAX_SOFTWARE_VOLUME = 0.78


# TODO move this to alarm, as it needs to be fade aware.
# TODO correct for fade duration
async def ring():
    """Ring."""
    global old
    old = enter_button["press"]
    enter_button["press"] = lambda _: alarm.cancel()
    logger.debug("ring ring")
    display.current_screen = ringing_screen
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
    except Exception:
        logger.exception("Error in ring")


async def end_alarm(*_):
    """Stop ringing."""
    asyncio.create_task(lamp.fade(duty=0))
    enter_button["press"] = old
    await mopidy_volume.fade(duty=0, duration=10)
    mute.on()
    await stop()
    await lcd.backlight.fade(duty=0)
    display.current_screen = main_screen


MIN_BRIGHTNESS = 0.03

fade_button_lock = asyncio.Lock()


async def fade_up_down(button):
    MANUAL_FADE_DURATION = 0.01
    async with fade_button_lock:
        if await lamp.get_duty() > 0:
            delta = -0.005
        else:
            delta = 0.005
            await lamp.set_percent_duty(MIN_BRIGHTNESS)
        while button.state:
            current = await lamp.get_percent_duty()
            await lamp.set_percent_duty(current + delta)
            await asyncio.sleep(MANUAL_FADE_DURATION)
        if await lamp.get_percent_duty() < MIN_BRIGHTNESS:
            await lamp.set_percent_duty(0)


async def up(*args):
    await lamp.set_percent_duty(await lamp.get_percent_duty() + 0.02)


async def down(*args):
    await lamp.set_percent_duty(await lamp.get_percent_duty() - 0.02)


async def incr():
    while up_button.state:
        await lamp.set_duty(await lamp.get_duty() + 1)


async def toggle_backlight(*args):
    if await lcd.backlight.get_percent_duty():
        await lcd.backlight.fade(percent_duty=0)
    else:
        await lcd.backlight.fade(percent_duty=1)


enter_button["long"] = fade_up_down


alarm = CachingAlarm(
    dbfile=Path("~/alarm.json").expanduser(),
    callback=ring,
    cancel_callback=end_alarm,
)
alarm.adjust_alarm = lambda val: (val - timedelta(seconds=FADE_DURATION))


def display_alarm(old, new):
    assert alarm.target
    main_screen[0] = "alarm {}: {}".format(
        "Off" if alarm.state == alarm.OFF else "On",
        alarm.target.strftime("%H:%M"),
    )


alarm._next_elapse.callback = display_alarm

display = LcdDisplay(lcd=lcd)
main_screen = display.new_screen("main-screen")
ringing_screen = display.new_screen("ringing")
ringing_screen[0] = "{:16}".format("Ring ring!")


def update_time(old, new):
    main_screen[1] = new
    ringing_screen[1] = new


timestr = Watched()
timestr.callback = update_time


async def clock_loop():
    while True:
        start = monotonic()
        timestr.value = "{:^16}".format(strftime("%H:%M:%S"))
        delay = 1 + start - monotonic()
        await asyncio.sleep(delay)


if not alarm.target:
    alarm.target = time(hour=8, minute=0)
loop = asyncio.get_event_loop()
loop.create_task(clock_loop())


async def backlight_on():
    await lcd.backlight.fade(percent_duty=1)


main_menu_item = MenuItem(
    next=None, prev=None, enter=None, screen=main_screen, entry_fn=toggle_backlight
)
main_menu_item.enter = main_menu_item

main_menu = Menu("main menu", main_menu_item)
main_menu.new_after(screen=ringing_screen, enter=None)
current_menu = main_menu
up_button["press"] = current_menu.next
down_button["press"] = current_menu.prev
enter_button["release"] = current_menu.enter


async def run() -> None: ...
