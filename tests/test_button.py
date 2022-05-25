import asyncio
from collections import namedtuple

import pytest
from rpi_clock.button import Button, PiButton

LONG_MS = 10
DOUBLE_MS = 6


ButtonConfig = namedtuple("ButtonConfig", "invert,coro")


@pytest.fixture(
    params=[
        ButtonConfig(invert=False, coro=False),
        ButtonConfig(invert=True, coro=False),
    ]
)
def button(request, mocker):
    b = Button(long_ms=LONG_MS, double_ms=DOUBLE_MS, inverted=request.param.invert)
    mock = mocker.Mock if not request.param.coro else mocker.AsyncMock
    b["press"] = mock()
    b["release"] = mock()
    b["double"] = mock()
    b["long"] = mock()
    b.coro = request.param.coro
    return b


def called_once(button, fn):
    verb = "awaited" if button.coro else "called"
    getattr(button[fn], f"assert_{verb}_once")()


def not_called(button, fn):
    verb = "awaited" if button.coro else "called"
    getattr(button[fn], f"assert_not_{verb}")()


def press(button: Button):
    print("--pressing--")
    if button.inverted:
        button._callback(0, Button.RISING_EDGE, 0)
    else:
        button._callback(0, Button.FALLING_EDGE, 0)


def release(button: Button):
    print("--releasing--")
    if button.inverted:
        button._callback(0, Button.FALLING_EDGE, 0)
    else:
        button._callback(0, Button.RISING_EDGE, 0)


async def sleep_ms(duration):
    await asyncio.sleep(duration / 1_000)


async def test_call_await(mocker, button):
    m = mocker.AsyncMock()
    await button.call(m)
    await sleep_ms(1)
    m.assert_awaited_once()


async def test_press(button):
    press(button)
    await sleep_ms(1)
    called_once(button, "press")
    not_called(button, "release")
    not_called(button, "double")
    not_called(button, "long")


async def test_press_coro(mocker, button):
    m = mocker.AsyncMock()
    button["press"] = m
    press(button)
    await sleep_ms(1)
    m.assert_awaited_once()
    not_called(button, "release")
    not_called(button, "double")
    not_called(button, "long")


async def test_press_release(button):
    await test_press(button)
    release(button)
    await sleep_ms(1)
    called_once(button, "press")
    called_once(button, "release")
    not_called(button, "double")
    not_called(button, "long")


async def test_long_press(button):
    press(button)
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    called_once(button, "press")
    called_once(button, "release")
    not_called(button, "double")
    called_once(button, "long")


async def test_double_press(button):
    for _ in range(2):
        press(button)
        await sleep_ms(0.5)
        release(button)
        await sleep_ms(0.5)

    not_called(button, "long")
    called_once(button, "double")
    assert sum(1 for x in button["press"].mock_calls if "bool" not in repr(x)) == 2
    assert sum(1 for x in button["release"].mock_calls if "bool" not in repr(x)) == 2


async def test_double_press_only(button):
    del button["long"]
    del button["release"]
    del button["press"]
    for _ in range(2):
        press(button)
        await sleep_ms(0.5)
        release(button)
        await sleep_ms(0.5)

    called_once(button, "double")


async def test_single_press_suppress(button):
    button.suppress = True
    del button["press"]
    del button["double"]
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    called_once(button, "release")
    not_called(button, "long")


async def test_long_hold(button):
    del button["press"]
    press(button)
    await sleep_ms(LONG_MS + 1)
    called_once(button, "long")
    release(button)
    await sleep_ms(1)
    called_once(button, "release")
    not_called(button, "double")


async def test_long_hold_suppress(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(LONG_MS + 1)
    called_once(button, "long")
    release(button)
    await sleep_ms(1)
    not_called(button, "release")
    not_called(button, "double")


async def test_single_press_suppress_double(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    not_called(button, "release")
    not_called(button, "long")
    await sleep_ms(DOUBLE_MS)
    called_once(button, "release")
    not_called(button, "long")
    not_called(button, "double")


async def test_single_press_suppress_double(button):
    button.suppress = True
    del button["press"]
    del button["release"]
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    not_called(button, "long")
    await sleep_ms(DOUBLE_MS)
    not_called(button, "long")
    not_called(button, "double")


async def test_single_press_suppress_double_no_long(button):
    button.suppress = True
    del button["press"]
    del button["long"]
    press(button)
    await sleep_ms(DOUBLE_MS + 2)
    called_once(button, "release")
    not_called(button, "double")


async def test_single_press_suppress_long(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(LONG_MS + 5)
    not_called(button, "release")
    not_called(button, "double")
    called_once(button, "long")
    release(button)
    await sleep_ms(1)
    not_called(button, "release")


async def test_long_press_suppress(button):
    button.suppress = True
    del button["press"]
    del button["double"]
    press(button)
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    not_called(button, "release")
    called_once(button, "long")


async def test_long_press_suppress_double(button):
    button.suppress = True
    del button["press"]
    press(button)
    await sleep_ms(LONG_MS + 2)
    release(button)
    await sleep_ms(1)
    not_called(button, "release")
    not_called(button, "double")
    called_once(button, "long")


async def test_double_press_suppress(button):
    button.suppress = True
    del button["press"]
    for _ in range(2):
        press(button)
        await sleep_ms(1)
        release(button)
        await sleep_ms(1)
    not_called(button, "release")
    called_once(button, "double")
    not_called(button, "long")


def test_properties(button):
    assert button.double_ms == DOUBLE_MS
    button.double_ms = 2 * DOUBLE_MS
    assert button.double_ms == 2 * DOUBLE_MS

    assert button.long_ms == LONG_MS
    button.long_ms = 2 * LONG_MS
    assert button.long_ms == 2 * LONG_MS


def test_invalid_hook(button):
    with pytest.raises(ValueError):
        button["nonsuch"] = lambda x: x


async def test_invalid_edge(button):
    button._callback(0, 99, 0)
    task = next(
        x for x in asyncio.all_tasks() if "_button_check_loop" in x.get_coro().__name__
    )
    await sleep_ms(1)
    assert task.exception()


async def test_pibutton(mocker):
    pi = mocker.Mock()
    pin = mocker.Mock()
    button = PiButton(pi, pin, double_ms=DOUBLE_MS, long_ms=LONG_MS)
    assert button.double_ms == DOUBLE_MS
    assert button.long_ms == LONG_MS
    pi.set_glitch_filter.assert_called_once()
    pi.set_pull_up_down.assert_called_once()
    pi.set_mode.assert_called_once()
