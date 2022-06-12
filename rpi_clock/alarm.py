import asyncio
from datetime import datetime, time, timedelta
from typing import Optional

from . import run


class Alarm:
    """An alarm."""

    OFF = 0
    WAITING = 1
    IN_PROGRESS = 2

    def __init__(self, callback: Optional[callable] = None) -> None:
        """Set up the alarm."""
        self.callback = callback
        self._target: Optional[time] = None
        self.oneshot = False
        self._state = self.OFF
        self._waiter = asyncio.get_event_loop().create_task(self._schedule())

    @property
    def state(self):
        """Get alarm state."""
        return self._state

    @property
    def target(self) -> Optional[time]:
        """Get target time."""
        return self._target

    @target.setter
    def target(self, val: time):
        """Set target time."""
        self._waiter.cancel()
        self._target = val
        self._waiter = asyncio.create_task(self._schedule())

    async def _schedule(self):
        if not self._target:
            self._state = self.OFF
            return

        self._state = self.WAITING
        now = datetime.now()
        target = datetime.combine(now.date(), self._target)
        if target < now:
            tomorrow = now + timedelta(days=1)
            target = datetime.combine(tomorrow.date(), self._target)
        await asyncio.sleep((target - now).total_seconds())
        self._state = self.IN_PROGRESS
        if self.callback:
            await run(self.callback)
        if not self.oneshot:
            self.waiter = asyncio.create_task(self._schedule())
        else:
            self._state = self.OFF
