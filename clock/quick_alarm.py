import asyncio
from datetime import datetime, timedelta

from mopidy_asyncio_client import MopidyClient

from .hal import enter_button, lamp, lcd, mute, volume


async def play():
    async with MopidyClient(host="localhost") as mopidy:
        playlists = await mopidy.playlists.as_list()
        alarum = next(x["uri"] for x in playlists if x["name"] == "alarm")
        tracks = await mopidy.playlists.lookup(alarum)
        await mopidy.tracklist.clear()
        await mopidy.tracklist.add(uris=[x["uri"] for x in tracks["tracks"]])
        await mopidy.tracklist.shuffle()
        await mopidy.playback.play()


async def stop():
    async with MopidyClient(host="localhost") as mopidy:
        await mopidy.playback.stop()


old = None


async def end_alarm():
    await stop()
    print("fade off lamp")
    asyncio.create_task(lamp.fade(duty=0))
    print("fade off volume")
    await volume.fade(duty=0, duration=3)
    mute(True)
    print("restore button")
    enter_button["press"] = old


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
        print(gap)
        lcd[1] = "alarm: {}".format(next_elapse.strftime("%H:%M"))
        await asyncio.sleep(gap.seconds)
        old = enter_button["press"]
        enter_button["press"] = end_alarm
        print("ring ring")
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
