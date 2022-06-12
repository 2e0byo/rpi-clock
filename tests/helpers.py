import asyncio


async def sleep_ms(duration):
    """Sleep for ms."""
    await asyncio.sleep(duration / 1_000)
