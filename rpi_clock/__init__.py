import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

async def run(fn: Callable[[], T]) -> T:
    """Run a fn or coro."""
    x = fn()
    if asyncio.iscoroutine(x):
        x = await x
    return x
