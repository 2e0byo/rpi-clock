import asyncio

import pytest
from rpi_clock.button import Button

LONG_MS = 10
DOUBLE_MS = 2


@pytest.fixture
def button(mocker):
    b = Button(long_ms=LONG_MS, double_ms=DOUBLE_MS)
    b["press"] = mocker.Mock()
    b["release"] = mocker.Mock()
    b["double"] = mocker.Mock()
    b["long"] = mocker.Mock()
    return b


def press(button: Button):
    button._callback(0, Button.FALLING_EDGE, 0)


def release(button: Button):
    button._callback(0, Button.RISING_EDGE, 0)


async def test_press(button):
    press(button)
    await asyncio.sleep(0.001)
    button["press"].assert_called_once()
    button["release"].assert_not_called()
    button["double"].assert_not_called()
    button["long"].assert_not_called()


async def test_press_release(button):
    await test_press(button)
    release(button)
    await asyncio.sleep(0.001)
    button["press"].assert_called_once()
    button["release"].assert_called_once()
    button["double"].assert_not_called()
    button["long"].assert_not_called()
