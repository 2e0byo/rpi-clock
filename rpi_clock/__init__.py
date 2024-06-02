import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

async def run(fn: Callable[[], T] | None) -> T | None:
    """Run a fn or coro."""
    if fn:
        x = fn()
        if asyncio.iscoroutine(x):
            x = await x
        return x
    if asyncio.iscoroutine(x):
        x = await x
    return x
