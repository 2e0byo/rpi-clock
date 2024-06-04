from typing import Never
import uvicorn
import typer

from . import api
from .clock import loop

app = typer.Typer()


async def start_server(config: uvicorn.Config) -> Never:
    server = uvicorn.Server(config)
    await server.serve()


@app.command(help="Run clock")
def main(port: int=8000) -> None:
    config = uvicorn.Config(api.app, host="0.0.0.0", port=port)
    loop.create_task(start_server(config))
    loop.run_forever()


if __name__ == "__main__":
    app()
