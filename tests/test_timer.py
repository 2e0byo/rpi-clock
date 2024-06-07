import asyncio

import pytest

from rpi_clock.timer import Timer


async def run_timed(t: Timer):
    ms = 0
    t.trigger()
    while t.running:
        await asyncio.sleep(0.001)
        ms += 1
    return ms


async def test_duration():
    t = Timer(duration_ms=10)
    assert t.duration == 10
    assert await run_timed(t) == pytest.approx(10, rel=1)

    t.duration += 10
    assert t.duration == 20
    assert await run_timed(t) == pytest.approx(20, rel=1)


async def test_cancel_running():
    t = Timer(duration_ms=10)
    t.trigger()
    assert t.running
    t.cancel()
    assert not t.running


async def test_fn(mocker):
    fn = mocker.MagicMock()
    t = Timer(duration_ms=10, fn=fn)
    t.trigger()
    await asyncio.sleep(0.011)
    assert not t.running
    fn.assert_called_once()


async def test_coro(mocker):
    state = False

    async def fn():
        nonlocal state
        await asyncio.sleep(0.001)
        state = True

    t = Timer(duration_ms=10, fn=fn)
    t.trigger()
    while t.running:
        await asyncio.sleep(0.001)
    assert state


async def test_cancel_coro():
    started, ended = False, False

    async def fn():
        nonlocal started, ended
        started = True
        await asyncio.sleep(1)
        ended = True

    t = Timer(duration_ms=10, fn=fn)
    t.trigger()
    await asyncio.sleep(0.015)
    t.cancel()
    assert started
    assert not ended
