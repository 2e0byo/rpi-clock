from typing import Never

import typer
import uvicorn

from .config import Settings
from .log import setup_logging

setup_logging(Settings().log_level)

from . import api, hal  # noqa: E402
from .clock import loop  # noqa: E402

app = typer.Typer()


async def start_server(config: uvicorn.Config) -> Never:
    server = uvicorn.Server(config)
    await server.serve()


def setup_hardware() -> None:
    hal.mute.on()


@app.command(help="Run clock")
def main(port: int = 8000) -> None:
    setup_hardware()
    config = uvicorn.Config(api.app, host="0.0.0.0", port=port)
    loop.create_task(start_server(config))
    loop.run_forever()


if __name__ == "__main__":
    app()
