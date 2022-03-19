import asyncio

import pytest
from rpi_clock.fadeable import PWM, Fadeable, Lamp


def async_return(result):
    # https://stackoverflow.com/a/50031903/15452601
    f = asyncio.Future()
    f.set_result(result)
    return f


def concreter(abclass):
    # https://stackoverflow.com/a/37574495/15452601
    class concreteCls(abclass):
        pass

    concreteCls.__abstractmethods__ = frozenset()
    return type("DummyConcrete" + abclass.__name__, (concreteCls,), {})


def mock_duty(x=None, val=[0]):
    if x is not None:
        val[0] = x
    else:
        return val[0]


def mock_fadeable(mocker, start):
    f = concreter(Fadeable)
    duty_mock = mocker.PropertyMock(return_value=start)
    f.duty = duty_mock
    f.max_duty = 50
    f.MAX_FADE_FREQ_HZ = 1_000_000  # prevent it from getting in the way
    f = f()
    return f, duty_mock


@pytest.mark.parametrize(
    "start, end",
    [
        [50, 0],
        [0, 50],
        [10, 20],
        [20, 10],
    ],
)
async def test_fade(mocker, start, end):
    f, duty_mock = mock_fadeable(mocker, start)
    await f.fade(duty=end, duration=0.01)
    step = -1 if end < start else 1
    duty_mock.assert_has_calls([mocker.call(x) for x in range(start, step, end + step)])


async def test_fade_freq(mocker):
    f, duty_mock = mock_fadeable(mocker, 0)
    f.MAX_FADE_FREQ_HZ = 90
    await f.fade(duty=50, duration=0.1)
    assert duty_mock.call_count < 50


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
    f, duty_mock = mock_fadeable(mocker, round(50 * start))
    await f.fade(percent_duty=end, duration=0.01)
    step = -1 if end < start else 1
    duty_mock.assert_called_with(round(end * 50))
    assert duty_mock.call_count > 10


async def test_cancel_fade(mocker):
    f, duty_mock = mock_fadeable(mocker, 0)
    asyncio.create_task(f.fade(percent_duty=1, duration=1))
    await asyncio.sleep(0.1)
    task = f._fade_task
    assert not task.done()
    f.cancel_fade()
    await asyncio.sleep(0.1)
    assert task.cancelled()


@pytest.mark.parametrize(
    "real, percent",
    [
        [0, 0],
        [50, 1],
        [25, 0.5],
    ],
)
def test_percent_duty(mocker, real, percent):
    f, _ = mock_fadeable(mocker, real)
    assert f.percent_duty == percent
    f, mock_duty = mock_fadeable(mocker, 0)
    f.percent_duty = percent
    mock_duty.assert_called_with(real)


def test_percent_duty_bounding(mocker):
    f, mock_duty = mock_fadeable(mocker, 0)
    f.percent_duty = -1
    mock_duty.assert_called_with(0)
    f.percent_duty = 2
    mock_duty.assert_called_with(50)
