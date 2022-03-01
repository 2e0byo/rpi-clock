from .hal import lamp, lcd, up_button, down_button, enter_button
from datetime import datetime, timedelta
from .quick_alarm import alarm
import asyncio
from functools import partial
from time import monotonic, strftime, sleep


def up(*args):
    lamp.percent_duty += 0.02


def down(*args):
    lamp.percent_duty -= 0.02


async def incr():
    while up_button.state:
        lamp.duty += 1
        # await asyncio.sleep(0.1)


up_button["press"] = up
# up_button["long"] = incr
down_button["press"] = down


async def toggle_backlight(*args):
    if lcd.backlight.percent_duty:
        await lcd.backlight.fade(0)
    else:
        await lcd.backlight.fade(lcd.backlight.max_duty)


enter_button["press"] = toggle_backlight


async def clock_loop():
    while True:
        start = monotonic()
        lcd[0] = "{:^16}".format(strftime("%H:%M:%S"))
        delay = 1 + start - monotonic()
        await asyncio.sleep(delay)


loop = asyncio.get_event_loop()
loop.create_task(alarm(datetime(year=2022, month=2, day=28, hour=8, minute=0).time()))
# loop.create_task(alarm((datetime.now() + timedelta(seconds=3)).time()))
loop.create_task(clock_loop())
loop.run_forever()
