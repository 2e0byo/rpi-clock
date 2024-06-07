import asyncio
from collections import namedtuple

import pytest
from gpiozero.pins.mock import MockFactory
from helpers import sleep_ms

from rpi_clock.button import Button, PiButton, ZeroButton

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
    print("--pressing--")  # noqa: T201
    if button.inverted:
        button._callback(Button.RISING_EDGE)
    else:
        button._callback(Button.FALLING_EDGE)


def release(button: Button):
    print("--releasing--")  # noqa: T201
    if button.inverted:
        button._callback(Button.FALLING_EDGE)
    else:
        button._callback(Button.RISING_EDGE)


class StateDependantCallback:
    def __init__(self):
        self.state = None

    async def __call__(self, btn):
        self.state = btn.state
        while btn.state is self.state:
            await sleep_ms(0)
        self.state = btn.state


async def test_call_await(mocker, button):
    m = mocker.AsyncMock()
    button["press"] = m
    await button.call("press")
    await sleep_ms(1)
    m.assert_awaited_once()


class Blocker:
    def __init__(self):
        self.blocked = True
        self.called = False

    async def __call__(self, btn):
        self.called = True
        while self.blocked:
            await sleep_ms(1)


async def test_blocking_call(mocker, button):
    button.blocking = True
    button["press"] = Blocker()
    button["release"] = mocker.AsyncMock()
    assert not button.in_progress
    asyncio.create_task(button.call("press"))
    await sleep_ms(1)
    assert button["press"].called
    asyncio.create_task(button.call("release"))
    await sleep_ms(1)
    not_called(button, "release")
    button["press"].blocked = False
    await sleep_ms(1)
    asyncio.create_task(button.call("release"))
    await sleep_ms(1)
    called_once(button, "release")


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


async def test_single_press_suppress_double_release(button):
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
    button._callback(99)
    task = next(
        x for x in asyncio.all_tasks() if "_button_check_loop" in x.get_coro().__name__
    )
    await sleep_ms(1)
    assert task.exception()


async def test_pibutton(mocker):
    pi = mocker.Mock()
    pin = mocker.Mock()
    button = PiButton(pi, pin, double_ms=DOUBLE_MS, long_ms=LONG_MS, name="Buttonhole")
    assert button.double_ms == DOUBLE_MS
    assert button.long_ms == LONG_MS
    assert button.name == "Buttonhole"
    pi.set_glitch_filter.assert_called_once()
    pi.set_pull_up_down.assert_called_once()
    pi.set_mode.assert_called_once()


def test_dump(button):
    fns = {k: button.pop(k) for k in button}
    assert not button["long"]
    assert not button["press"]
    assert not button["release"]
    assert not button["double"]
    button |= fns
    assert button["long"]
    assert button["press"]
    assert button["release"]
    assert button["double"]


async def test_press_state_depending(button):
    callback = StateDependantCallback()
    button["press"] = callback
    assert not callback.state
    assert not button.state
    press(button)
    await sleep_ms(1)
    assert callback.state
    release(button)
    await sleep_ms(2)
    assert not callback.state


async def test_long_state_depending(button):
    callback = StateDependantCallback()
    button["long"] = callback
    assert not callback.state
    assert not button.state
    press(button)
    await sleep_ms(LONG_MS + 1)
    assert callback.state
    release(button)
    await sleep_ms(2)
    assert not button.state
    assert not callback.state


async def test_double_state_depending(button):
    callback = StateDependantCallback()
    button.suppress = True
    button["double"] = callback
    assert not callback.state
    assert not button.state
    press(button)
    await sleep_ms(1)
    release(button)
    await sleep_ms(1)
    press(button)
    await sleep_ms(2)
    assert callback.state
    release(button)
    await sleep_ms(2)
    assert not button.state
    assert not callback.state


def test_name():
    b = Button(name="Buttonhole")
    assert b.name == "Buttonhole"


async def test_dying_callback(mocker, button):
    e = Exception("Failed")

    def callback(*_):
        raise e

    button["press"] = callback
    del button["release"]
    del button["long"]
    del button["double"]
    button._logger = mocker.Mock()
    press(button)
    await sleep_ms(1)
    button._logger.error.assert_called_with(e)


async def test_zero_button():
    b = ZeroButton(1, pin_factory=MockFactory())
    b._pin.drive_low()
    await sleep_ms(2)
    assert b.state
    b._pin.drive_high()
    await sleep_ms(2)
    assert not b.state


def test_zero_button_debounce():
    b = ZeroButton(1, pin_factory=MockFactory(), debounce_ms=100)
    assert b._pin.bounce == 0.1
