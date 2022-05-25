import asyncio
from datetime import datetime, timedelta
from functools import partial
from logging import getLogger
from time import monotonic, sleep, strftime

from mopidy_asyncio_client import MopidyClient

from rpi_clock.fadeable import SpiError
from rpi_clock.hal import down_button, enter_button, lamp, lcd, mute, up_button, volume

logger = getLogger(__name__)


async def queue_playlist(mopidy, name: str):
    playlists = await mopidy.playlists.as_list()
    playlist = next(x["uri"] for x in playlists if x["name"] == name)
    tracks = await mopidy.playlists.lookup(playlist)
    await mopidy.tracklist.add(uris=[x["uri"] for x in tracks["tracks"]])


async def play():
    async with MopidyClient(host="localhost") as mopidy:
        await mopidy.tracklist.clear()
        await queue_playlist(mopidy, "alarm")
        await mopidy.tracklist.shuffle()
        await mopidy.playback.play()


async def stop():
    async with MopidyClient(host="localhost") as mopidy:
        await mopidy.playback.stop()


old = None


async def end_alarm(button):
    await stop()
    logger.debug("fade off lamp")
    asyncio.create_task(lamp.fade(duty=0))
    logger.debug("restore button")
    enter_button["press"] = old
    logger.debug("fade off volume")
    await volume.fade(duty=0, duration=3)
    mute(True)


FADE_DURATION = 300
# FADE_DURATION = 10
START_VOLUME = 4 / 50
MAX_VOLUME = 11 / 50


async def alarm(when: datetime.time):
    global old
    while True:
        now = datetime.now()
        next_elapse = datetime.combine(now.date(), when)
        if now > next_elapse:
            next_elapse += timedelta(days=1)
        gap = next_elapse - datetime.now()
        logger.debug(gap)
        lcd[1] = "alarm: {}".format(next_elapse.strftime("%H:%M"))
        await asyncio.sleep(gap.seconds)
        old = enter_button["press"]
        enter_button["press"] = end_alarm
        logger.debug("ring ring")
        lcd[1] = "ring ring"
        try:
            await lamp.fade(duty=500, duration=FADE_DURATION)
            await play()
            mute(False)
            volume.percent_duty = START_VOLUME
            asyncio.create_task(volume.fade(percent_duty=MAX_VOLUME, duration=30))
            asyncio.create_task(lcd.backlight.fade(percent_duty=1))
        except asyncio.CancelledError:
            pass


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


loop = asyncio.get_event_loop()
loop.create_task(alarm(datetime(year=2022, month=2, day=28, hour=9, minute=30).time()))
# loop.create_task(alarm((datetime.now() + timedelta(seconds=3)).time()))
loop.create_task(clock_loop())
loop.run_forever()
