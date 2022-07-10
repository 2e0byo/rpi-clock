import asyncio

import pytest
from gpiozero.pins.mock import MockFactory
from rpi_clock.fadeable import (
    PWM,
    Device,
    Fadeable,
    Lamp,
    MockFadeable,
    SpiControllerError,
    SPIFixedRate,
)


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


async def test_no_duty():
    f = MockFadeable()
    with pytest.raises(ValueError):
        await f.fade()


async def test_pwm(mocker):
    mocker.patch("rpi_clock.fadeable.HardwarePWM")
    f = PWM(0)
    f.pwm.start.assert_called_once_with(0)
    await f.set_duty(56)
    f.pwm.change_duty_cycle.assert_called_once_with(56)
    f.pwm._duty_cycle = 56
    assert await f.get_duty() == 56


@pytest.fixture
def lamp(mocker):
    Device.pin_factory = MockFactory()
    f = Lamp(pin_factory=MockFactory())
    f.spi.transfer = mocker.Mock()
    yield f
    f.spi.close()


async def test_spi_rate_success(mocker):
    Device.pin_factory = MockFactory()
    spi = mocker.Mock()
    rate = mocker.PropertyMock()
    type(spi).rate = rate
    pin_factory = MockFactory()
    pin_factory.spi = mocker.Mock()
    pin_factory.spi.return_value = spi

    f = Lamp(pin_factory=pin_factory)
    assert f.spi == spi
    rate.assert_called_once()


async def test_spi_rate_failure(mocker):
    Device.pin_factory = MockFactory()
    spi = mocker.Mock()
    rate = mocker.PropertyMock()

    def die(*_):
        raise SPIFixedRate("test")

    rate.side_effect = die
    type(spi).rate = rate
    pin_factory = MockFactory()
    pin_factory.spi = mocker.Mock()
    pin_factory.spi.return_value = spi

    f = Lamp(pin_factory=pin_factory)
    rate.assert_called_once()


def _to_bytestr(x):
    return b"s" + int(x).to_bytes(2, "little")


async def test_lamp_set_get(lamp, mocker):
    bytestr = _to_bytestr(150)
    lamp.spi.transfer.return_value = bytestr[1:]
    await lamp.set_duty(150)
    lamp.spi.transfer.assert_any_call(bytestr)
    assert await lamp.get_duty() == 150
    assert await lamp.get_hardware_duty() == 150


async def test_repeate_set(lamp, mocker):
    bytestr = _to_bytestr(150)
    calls = 0
    lamp._logger = mocker.Mock()

    def fail_once(*_):
        nonlocal calls
        calls += 1
        if calls > 4:  # called twice per setting
            return bytestr[1:]
        else:
            return _to_bytestr(0)

    lamp.spi.transfer = fail_once
    lamp._zero_task.cancel()
    await lamp.set_duty(150)
    assert calls == 6
    lamp._logger.debug.assert_called_with("Set lamp to 150 after 2 attempts.")


async def test_fail(lamp, mocker):
    lamp.spi.transfer.return_value = b"\x00\x00"
    lamp.reset = mocker.AsyncMock()
    with pytest.raises(SpiControllerError):
        await lamp.set_duty(150)
    lamp.reset.assert_called()


async def test_reset(lamp, mocker):
    mocker.patch("rpi_clock.fadeable.asyncio.sleep", mocker.AsyncMock())
    cs = mocker.Mock()
    state = mocker.PropertyMock(return_value=1)
    type(cs).state = state
    lamp.cs = cs
    await lamp.reset()
    state.assert_has_calls([mocker.call(0), mocker.call(1)])
