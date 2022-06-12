import asyncio

import coloredlogs

coloredlogs.install()


async def run(fn: callable) -> any:
    """Run a fn or coro."""
    x = fn()
    if asyncio.iscoroutine(x):
        x = await x
    return x
