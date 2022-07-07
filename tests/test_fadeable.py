import asyncio

import pytest
from rpi_clock.fadeable import PWM, Fadeable, Lamp, MockFadeable


async def test_set_duty():
    f = MockFadeable()
    await f.set_duty(51)
    f.set_duty_mock.assert_called_once_with(51)
    f.get_duty_mock.assert_not_called()
    assert await f.get_duty() == 51
    f.get_duty_mock.assert_called_once()


async def test_set_out_of_range():
    f = MockFadeable()
    await f.set_duty(999999)
    assert await f.get_duty() == f.max_duty
    await f.set_duty(-100)
    assert await f.get_duty() == 0


@pytest.mark.parametrize(
    "real, percent",
    [
        [0, 0],
        [100, 1],
        [50, 0.5],
    ],
)
async def test_percent_duty(real, percent):
    f = MockFadeable()
    await f.set_percent_duty(percent)
    assert await f.get_percent_duty() == percent
    assert await f.get_duty() == real
    f.set_duty_mock.assert_called_once_with(real)


async def test_percent_duty_bounding(mocker):
    f = MockFadeable()
    await f.set_percent_duty(-1)
    assert await f.get_duty() == 0

    await f.set_percent_duty(2)
    assert await f.get_duty() == 100


@pytest.mark.parametrize(
    "start, end",
    [
        [0, 50],
        [10, 20],
        [20, 10],
        [50, 50],
        [50, 0],
        [0, 100],
        [100, 0],
    ],
)
async def test_fade(mocker, start, end):
    f = MockFadeable()
    await f.set_duty(start)
    await f.fade(duty=end, duration=0.01)
    step = -1 if end < start else 1
    f.set_duty_mock.assert_has_calls(
        [mocker.call(x) for x in range(start, end + step, step)]
    )


async def test_fade_freq():
    f = MockFadeable()
    f.max_fade_freq_hz = 90
    await f.fade(duty=50, duration=0.1)
    assert f.set_duty_mock.call_count == pytest.approx(9, 1)


async def test_invalid_fade(mocker):
    f = MockFadeable()
    with pytest.raises(ValueError):
        await f.fade(duration=10)


@pytest.mark.parametrize(
    "start, end",
    [
        [1, 0],
        [0, 1],
        [0.5, 0.7],
        [0.7, 0.5],
    ],
)
async def test_percent_fade(mocker, start, end):
    f = MockFadeable()
    await f.set_percent_duty(start)
    await f.fade(percent_duty=end, duration=0.01)
    f.set_duty_mock.assert_called_with(round(end * f.max_duty))
    assert f.set_duty_mock.call_count > 10


async def test_cancel_fade(mocker):
    f = MockFadeable()
    asyncio.create_task(f.fade(percent_duty=1, duration=1))
    await asyncio.sleep(0.1)
    task = f._fade_task
    assert not task.done()
    f.cancel_fade()
    await asyncio.sleep(0.1)
    assert task.cancelled()


async def test_pwm(mocker):
    mocker.patch("rpi_clock.fadeable.HardwarePWM")
    f = PWM(0)
    f.pwm.start.assert_called_once_with(0)
    await f.set_duty(56)
    f.pwm.change_duty_cycle.assert_called_once_with(56)
    f.pwm._duty_cycle = 56
    assert await f.get_duty() == 56
