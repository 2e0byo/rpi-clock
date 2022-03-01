import asyncio

import pytest
from rpi_clock.fadeable import PWM, Fadeable, Lamp


def async_return(result):
    # https://stackoverflow.com/a/50031903/15452601
    f = asyncio.Future()
    f.set_result(result)
    return f


async def test_fade(mocker):
    f = Fadeable()
    f.duty = mocker.MagicMock()
    f.duty.return_value = async_return(0)
    await f.fade(50, 0.1)
    f.duty.assert_has_calls([mocker.call(x) for x in range(51)])
    f.duty.return_value = async_return(50)
    await f.fade(0, 0.1)
    f.duty.assert_has_calls([mocker.call(x) for x in range(50, -1, -1)])
