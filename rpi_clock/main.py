from typing import Never
import uvicorn

from .api import app
from .clock import loop


async def start_server() -> Never:
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

def main() -> None:
    loop.create_task(start_server())
    loop.run_forever()

