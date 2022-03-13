import asyncio
from datetime import datetime, timedelta
from mopidy_asyncio_client import MopidyClient
from .hal import volume, mute, lamp, enter_button, lcd


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
tasks = []


async def end_alarm():
    for task in tasks:
        try:
            task.cancel()
            print(task, "cancelled")
        except Exception:
            pass
    mute(True)
    await stop()
    print("fade off lamp")
    asyncio.create_task(lamp.fade(0))
    print("fade off volume")
    asyncio.create_task(volume.fade(0))
    print("restore button")
    enter_button["press"] = old


FADE_DURATION = 300
# FADE_DURATION = 10
MAX_VOLUME = 11


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
        await play()
        mute(False)
        x = lamp.fade(500, FADE_DURATION)
        tasks.append(x)
        await x
        tasks.append(asyncio.create_task(volume.fade(MAX_VOLUME, 30)))
