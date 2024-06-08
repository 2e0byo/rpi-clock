import asyncio
from typing import Callable

from . import run


class Timer:
    """Asyncio timer, api based loosely on Peter Hinch's Delay_ms."""

    def __init__(self, duration_ms=1_000, fn: Callable | None = None):
        """Set up the timer."""
        self.task = None
        self.loop = asyncio.get_event_loop()
        self._duration = duration_ms / 1_000
        self.fn: Callable | None = fn

    @property
    def duration(self):
        """Get the current duration, in seconds."""
        return self._duration * 1_000

    @duration.setter
    def duration(self, duration_ms: int):
        self._duration = duration_ms / 1_000

    def trigger(self):
        """Cancel and then launch the timer."""
        self.cancel()
        self.task = asyncio.create_task(self._trigger())

    def cancel(self):
        """Cancel the timer."""
        try:
            self.task.cancel()
            self.task = None
        except Exception:
            pass

    @property
    def running(self):
        """Whether the timer is currently running."""
        return bool(self.task)

    async def _call(self):
        await run(self.fn)

    async def _trigger(self):
        await asyncio.sleep(self._duration)
        if self.fn:
            await self._call()
        self.task = None
