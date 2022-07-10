import asyncio
import json
from datetime import datetime, time, timedelta
from logging import getLogger
from pathlib import Path
from typing import Optional

from . import run
from .endpoint import Endpoint


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
        self._real_target: Optional[time] = None
        self.oneshot = False
        self._state = self.OFF
        self._waiter = asyncio.get_event_loop().create_task(self._schedule())
        name = name or f"Alarm-{self.instances}"
        self.instances += 1
        self._logger = getLogger(name)
        self._next_elapse: Optional[datetime] = None
        self.adjust_alarm = lambda val: val

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
        self._waiter = asyncio.get_event_loop().create_task(self._schedule())

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
        target = self.adjust_alarm(target)
        self._logger.debug(f"Alarm will go off in {(target-now)}")
        await asyncio.sleep((target - now).total_seconds())
        self._state = self.IN_PROGRESS
        self._logger.debug("Ring ring!")
        if self.callback:
            await run(self.callback)
        if not self.oneshot:
            self.waiter = asyncio.create_task(self._schedule())
        else:
            self._state = self.OFF


class CachingAlarm(Alarm):
    """An alarm which remembers its setpoints."""

    def __init__(self, *args, dbfile: Path, **kwargs):
        """Initialise a new CachingAlarm."""
        self.dbfile = dbfile
        super().__init__(*args, **kwargs)
        if target := self._load():
            self.target = target

    def _load(self):
        try:
            with self.dbfile.open() as f:
                data = json.load(f)
                return time.fromisoformat(data["value"])
        except Exception:
            return None

    def _save(self):
        with self.dbfile.open("w") as f:
            json.dump({"value": str(self.target)}, f)

    @property
    def target(self):
        """Get alarm target."""
        return super().target

    @target.setter
    def target(self, val):
        """Set alarm target and save."""
        super(CachingAlarm, self.__class__).target.fset(self, val)
        self._save()


class AlarmEndpoint(Endpoint[Alarm]):
    """An endpoint to control an alarm."""

    def __init__(self, *args, **kwargs):
        """Initialise a new alarm endpoint."""
        super().__init__(*args, **kwargs)
        self.router.get("/next-elapse")(self.next_elapse)
        self.router.get("/")(self.get_target)
        self.router.put("/")(self.set_target)

    def next_elapse(self) -> Optional[datetime]:
        """Get next elapse point."""
        return self.thing.next_elapse

    # These are async to force them to be in the main thread
    async def get_target(self) -> Optional[datetime]:
        """Get alarm target."""
        return self.thing.target

    async def set_target(self, val: time) -> Optional[datetime]:
        """Set alarm target."""
        self.thing.target = val
        return await self.get_target()
