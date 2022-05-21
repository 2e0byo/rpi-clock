import asyncio

import pytest
from rpi_clock.button import Button

LONG_MS = 10
DOUBLE_MS = 6


@pytest.fixture
def button(mocker):
    b = Button(long_ms=LONG_MS, double_ms=DOUBLE_MS)
    b["press"] = mocker.Mock()
    b["release"] = mocker.Mock()
    b["double"] = mocker.Mock()
    b["long"] = mocker.Mock()
    return b


def press(button: Button):
    print("--pressing--")
    button._callback(0, Button.FALLING_EDGE, 0)


def release(button: Button):
    print("--releasing--")
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
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    button["press"].assert_called_once()
    button["release"].assert_called_once()
    button["double"].assert_not_called()
    button["long"].assert_called_once()


async def test_double_press(button):
    for _ in range(2):
        press(button)
        await sleep_ms(0.5)
        release(button)
        await sleep_ms(0.5)

    button["long"].assert_not_called()
    button["double"].assert_called_once()
    assert len(button["press"].mock_calls) == 2
    assert len(button["release"].mock_calls) == 2


async def test_single_press_suppress(button):
    button.suppress = True
    del button["press"]
    del button["double"]
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    button["release"].assert_called_once()
    button["long"].assert_not_called()


async def test_single_press_suppress_double(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    button["release"].assert_not_called()
    button["long"].assert_not_called()
    await sleep_ms(DOUBLE_MS)
    button["release"].assert_called_once()
    button["long"].assert_not_called()
    button["double"].assert_not_called()


async def test_long_press_suppress(button):
    button.suppress = True
    del button["press"]
    del button["double"]
    press(button)
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    button["release"].assert_not_called()
    button["long"].assert_called_once()


async def test_long_press_suppress_double(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    button["release"].assert_not_called()
    button["double"].assert_not_called()
    button["long"].assert_called_once()


async def test_double_press_suppress(button):
    button.suppress = True
    del button["press"]
    for _ in range(2):
        press(button)
        await sleep_ms(1)
        release(button)
        await sleep_ms(1)
    button["release"].assert_not_called()
    button["double"].assert_called_once()
    button["long"].assert_not_called()


def test_properties(button):
    assert button.double_ms == DOUBLE_MS
    button.double_ms = 2 * DOUBLE_MS
    assert button.double_ms == 2 * DOUBLE_MS

    assert button.long_ms == LONG_MS
    button.long_ms = 2 * LONG_MS
    assert button.long_ms == 2 * LONG_MS
