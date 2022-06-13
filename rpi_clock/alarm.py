import asyncio
from datetime import datetime, time, timedelta
from logging import getLogger
from typing import Optional

from . import run


class Alarm:
    """An alarm."""

    OFF = 0
    WAITING = 1
    IN_PROGRESS = 2
    instances = 0

    def __init__(
        self, callback: Optional[callable] = None, name: Optional[str] = None
    ) -> None:
        """Set up the alarm."""
        self.callback = callback
        self._target: Optional[time] = None
        self.oneshot = False
        self._state = self.OFF
        self._waiter = asyncio.get_event_loop().create_task(self._schedule())
        name = name or f"Alarm-{self.instances}"
        self.instances += 1
        self._logger = getLogger(name)
        self._next_elapse: Optional[datetime] = None

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

    @property
    def next_elapse(self) -> Optional[datetime]:
        """Get next elapse point."""
        if self.state == self.OFF:
            return None
        return self._next_elapse

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
        self._next_elapse = target
        self._logger.debug(f"Alarm will go off in {(target-now)}")
        await asyncio.sleep((target - now).total_seconds())
        self._state = self.IN_PROGRESS
        if self.callback:
            await run(self.callback)
        if not self.oneshot:
            self.waiter = asyncio.create_task(self._schedule())
        else:
            self._state = self.OFF
