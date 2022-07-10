import asyncio
import json
from datetime import datetime, time, timedelta

import pytest
from rpi_clock.alarm import Alarm, CachingAlarm

from helpers import sleep_ms


@pytest.fixture
def alarm(mocker):
    return Alarm(callback=mocker.MagicMock())


async def test_set_alarm(alarm):
    assert alarm.state == alarm.OFF
    assert not alarm.oneshot
    assert not alarm.target
    alarm.target = (datetime.now() + timedelta(seconds=1)).time()
    await sleep_ms(3)
    assert alarm.state == alarm.WAITING
    await asyncio.sleep(1.1)
    assert alarm.state == alarm.WAITING
    alarm.callback.assert_called_once()


def test_set_alarm_noloop(alarm):
    alarm.target = (datetime.now() + timedelta(seconds=1)).time()


async def test_alarm_no_callback(alarm):
    alarm.callback = None
    assert alarm.state == alarm.OFF
    alarm.oneshot = True
    assert not alarm.target
    alarm.target = (datetime.now() + timedelta(seconds=1)).time()
    await sleep_ms(3)
    assert alarm.state == alarm.WAITING
    await asyncio.sleep(1.1)
    assert alarm.state == alarm.OFF


async def test_set_alarm_oneshot(alarm):
    assert alarm.state == alarm.OFF
    alarm.oneshot = True
    assert not alarm.target
    alarm.target = (datetime.now() + timedelta(seconds=1)).time()
    await sleep_ms(3)
    assert alarm.state == alarm.WAITING
    await asyncio.sleep(1.1)
    assert alarm.state == alarm.OFF
    alarm.callback.assert_called_once()


async def test_next_elapse(alarm):
    assert not alarm.next_elapse
    elapse = datetime.now() - timedelta(hours=4)
    alarm.target = elapse.time()
    await sleep_ms(1)
    assert alarm.state == alarm.WAITING
    elapse += timedelta(days=1)
    assert alarm.next_elapse == elapse


async def test_caching_alarm(tmp_path):
    alarmf = tmp_path / "alarm.json"
    alarm = CachingAlarm(dbfile=alarmf)
    assert alarm.target != time(8, 10)
    alarm.target = time(8, 10)
    assert alarmf.exists()
    assert json.loads(alarmf.read_text())["value"] == "08:10:00"
    del alarm
    alarm = CachingAlarm(dbfile=alarmf)
    assert alarm.target == time(8, 10)
