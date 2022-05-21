import asyncio


class Timer:
    """Asyncio timer, api based loosely on Peter Hinch's Delay_ms."""

    def __init__(self, duration_ms=1_000, fn: callable = None):
        self.task = None
        self.loop = asyncio.get_event_loop()
        self._duration = duration_ms / 1_000
        self.fn: callable = fn

    @property
    def duration(self):
        return self._duration * 1_000

    @duration.setter
    def duration(self, duration_ms: int):
        self._duration = duration_ms / 1_000

    def trigger(self):
        self.cancel()
        self.task = asyncio.create_task(self._trigger())

    def cancel(self):
        try:
            self.task.cancel()
            self.task = None
        except Exception:
            pass

    @property
    def running(self):
        return bool(self.task)

    async def _call(self):
        x = self.fn()
        if asyncio.iscoroutine(x):
            await x

    async def _trigger(self):
        await asyncio.sleep(self._duration)
        if self.fn:
            await self._call()
        self.task = None
