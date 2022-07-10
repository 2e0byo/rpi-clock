import uvicorn

from rpi_clock.api import app
from rpi_clock.clock import loop


async def start_server():
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    loop.create_task(start_server())
    loop.run_forever()
