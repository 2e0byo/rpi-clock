import asyncio
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable, Optional, Union, cast

from structlog import get_logger

from . import run
from .endpoint import Endpoint
from .reactive import Watched

logger = get_logger()


class Alarm:
    """An alarm."""

    OFF = "OFF"
    WAITING = "WAITING"
    IN_PROGRESS = "IN PROGRESS"
    instances = 0
    TICK_S = 1

    def __init__(
        self,
        *,
        callback: Callable,
        cancel_callback: Optional[Callable] = None,
        snooze_callback: Optional[Callable[[], None]] = None,
        elapsed_callback: Optional[Callable[[], None]] = None,
        name: Optional[str] = None,
    ) -> None:
        """Set up the alarm."""
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.snooze_callback = snooze_callback
        self.elapsed_callback = elapsed_callback
        self._saved_target: Optional[time] = None
        self._target: Union[time, None, bool] = None
        self._real_target: Optional[time] = None
        self.oneshot = False
        self._saved_oneshot = True
        self._state = self.OFF
        self._waiter = asyncio.get_event_loop().create_task(self._schedule())
        self.name = name or f"Alarm-{self.instances}"
        self.instances += 1
        self._logger = logger.bind(name=self.name)
        self._next_elapse: Watched[Optional[datetime]] = Watched()
        self.adjust_alarm = lambda val: val
        self._enabled = True
        self._snoozing = False
        self._cancel_event = asyncio.Event()

    @property
    def state(self):
        """Get alarm state."""
        return self._state

    @property
    def target(self) -> Optional[time]:
        """Get target time."""
        if self._target is True:
            return datetime.now().time()
        else:
            return cast(Optional[time], self._target)

    @target.setter
    def target(self, val: Union[time, None, bool]):
        """Set target time."""
        self._stop_waiting()
        self._target = val
        self._start_waiting()

    @property
    def next_elapse(self) -> Optional[datetime]:
        """Get next elapse point."""
        if self.state == self.OFF:
            return None
        return self._next_elapse.value

    @property
    def enabled(self):
        """Get current enabled state."""
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        if not val:
            self._stop_waiting()
        else:
            if self._state == self.OFF:
                self._start_waiting()

    @property
    def snoozing(self) -> bool:
        """Get whether alarm snoozing."""
        return self._snoozing

    def cancel(self) -> bool:
        """Cancel running alarm."""
        # sync runs on a different thread atm...
        # if self.cancel_callback:
        #     asyncio.create_task(run(self.cancel_callback))

        if self.state != self.IN_PROGRESS:
            self._logger.info(f"No need to cancel, currently {self.state}")
            return False
        else:
            self._logger.info("cancel")
            self._cancel_event.set()
            return True

    def _stop_waiting(self):
        async def _cancel(waiter):
            await asyncio.sleep(1)
            waiter.cancel()

        if self._waiter:
            self.cancel()
            if asyncio.get_event_loop().is_running():
                # run in asyncio thread to allow cleanup
                asyncio.create_task(_cancel(self._waiter))
            else:
                self._waiter.cancel()
        self._state = self.OFF

    def _start_waiting(self):
        if self._enabled:
            self._waiter = asyncio.get_event_loop().create_task(self._schedule())

    def snooze(self, duration: timedelta):
        """Snooze for a given duration."""
        # if self.snooze_callback:
        #     asyncio.create_task(run(self.snooze_callback))
        if not self._snoozing:
            self._saved_target = self.target
            self._saved_oneshot = self.oneshot
        self.oneshot = True
        if duration:
            self.target = (datetime.now() + duration).time()
        else:
            self.target = True
        self._waiter.add_done_callback(self._restore_target)
        self._snoozing = True
        self.cancel()

    def trigger(self):
        """Trigger immediately."""
        self.snooze(timedelta(seconds=0))

    def _restore_target(self, task):
        if task.cancelled():
            return
        self.oneshot = self._saved_oneshot
        self.target = self._saved_target
        self._snoozing = False

    async def _schedule(self):
        target_time = self._target
        if not target_time:
            self._state = self.OFF
            return

        self._state = self.WAITING
        if target_time is not True:
            now = datetime.now()
            target = datetime.combine(now.date(), target_time)
            if target < now:
                tomorrow = now + timedelta(days=1)
                target = datetime.combine(tomorrow.date(), target_time)
            self._next_elapse.value = target
            target = self.adjust_alarm(target)
            while datetime.now() < target:
                await asyncio.sleep(self.TICK_S)
        self._state = self.IN_PROGRESS
        self._logger.info(f"{self.name} elapsed.")
        asyncio.create_task(run(self.elapsed_callback))
        self._logger.debug("creating task")
        ring_task = asyncio.create_task(run(self.callback))
        self._logger.debug("waiting for event")
        await self._cancel_event.wait()
        self._logger.info("alarm over; cancelling")
        self._cancel_event.clear()
        ring_task.cancel()
        if self.cancel_callback:
            await run(self.cancel_callback)
        if self.oneshot:
            self._state = self.OFF
        else:
            self._waiter = asyncio.create_task(self._schedule())


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
        self.router.delete("/")(self.cancel)
        self.router.get("/enabled")(self.get_enabled)
        self.router.put("/enabled")(self.set_enabled)
        self.router.get("/state")(self.get_state)
        self.router.put("/snooze")(self.set_snooze)
        self.router.get("/snooze")(self.get_snooze)
        self.router.put("/trigger")(self.trigger)

    def next_elapse(self) -> Optional[datetime]:
        """Get next elapse point."""
        return self.thing.next_elapse

    # These are async to force them to be in the main thread
    async def get_target(self) -> Optional[time]:
        """Get alarm target."""
        return self.thing.target

    async def set_target(self, val: time) -> Optional[time]:
        """Set alarm target."""
        self.thing.target = val
        return await self.get_target()

    async def get_enabled(self) -> bool:
        """Get alarm enabled or not."""
        return self.thing.enabled

    async def set_enabled(self, val: bool) -> bool:
        """Set alarm enabled or not."""
        self.thing.enabled = val
        return await self.get_enabled()

    async def get_state(self):
        """Get alarm state."""
        return self.thing.state

    async def set_snooze(self, val: timedelta) -> time:
        """Set alarm snooze."""
        self.thing.snooze(val)
        return cast(time, await self.get_target())

    async def get_snooze(self) -> bool:
        """Get whether alarm snoozing."""
        return self.thing.snoozing

    async def cancel(self) -> bool:
        """Cancel alarm in progress (if any)."""
        return self.thing.cancel()

    async def trigger(self):
        """Trigger elapse."""
        self.thing.trigger()
