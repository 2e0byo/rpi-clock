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


async def sleep_ms(duration):
    await asyncio.sleep(duration / 1_000)


async def test_press(button):
    press(button)
    await sleep_ms(1)
    button["press"].assert_called_once()
    button["release"].assert_not_called()
    button["double"].assert_not_called()
    button["long"].assert_not_called()


async def test_press_release(button):
    await test_press(button)
    release(button)
    await sleep_ms(1)
    button["press"].assert_called_once()
    button["release"].assert_called_once()
    button["double"].assert_not_called()
    button["long"].assert_not_called()


async def test_long_press(button):
    press(button)
    sleep_ms(LONG_MS + 2)
    release(button)
    sleep_ms(1)
    button["press"].assert_called_once()
    button["release"].assert_called_once()
    button["double"].assert_not_called()
    button["long"].assert_called_once()


async def test_double_press(button):
    press(button)
    sleep_ms(1)
    release(button)
    sleep_ms(1)
    press(button)
    sleep_ms(1)
    release(button)
    sleep_ms(1)
    button["long"].assert_not_called()
    button["double"].assert_called_once()
    assert len(button["press"].mock_calls) == 2
    assert len(button["release"].mock_calls) == 2
