import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

# NOTE this api is terrible; just importing what was there.


async def run(fn: Callable[[], T] | None) -> T | None:
    """Run a fn or coro."""
    if fn:
        x = fn()
        if asyncio.iscoroutine(x):
            x = await x
        return x
    else:
        return None


def sync_run(fn: Callable[[], T] | None, *args, **kwargs) -> T | None:
    """Run a fn or schedule a coro, nonblocking."""
    if not fn:
        return None
    x = fn(*args, **kwargs)
    if asyncio.iscoroutine(x):
        # Can't get the result
        asyncio.create_task(x)
        return None
    else:
        return x
