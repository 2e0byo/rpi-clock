from typing import Iterator

from httpx import AsyncClient
from structlog import get_logger

from .fadeable import Fadeable

logger = get_logger()


def counter() -> Iterator[int]:
    i = 0
    while True:
        yield i
        i += 1


_ids = counter()


class MopidyRPC:
    def __init__(self, host: str = "localhost"):
        self.client = AsyncClient()
        self.url = f"http://{host}:6680/mopidy/rpc"

    async def post(self, **kwargs) -> dict:
        # TODO move client state up
        async with self.client as client:
            resp = await client.post(self.url, json=kwargs)
            resp.raise_for_status()
            return resp.json()

    async def rpc(self, method: str, *args, **kwargs):
        assert not (kwargs and args)
        data = await self.post(
            method=method, jsonrpc="2.0", id=next(_ids), params=kwargs or args
        )
        if "error" in data:
            raise ValueError(repr(data))
        else:
            return data["result"]


class MopidyVolume(Fadeable):
    """A volume, fadeable up and down."""

    def __init__(self, *args, host="localhost", **kwargs):
        """Initialise a `MopidyVolume` object."""
        self.client = MopidyRPC(host)
        self.max_duty = 100
        super().__init__(*args, **kwargs)

    async def get_hardware_duty(self):
        """Get volume duty."""
        return await self.client.rpc("core.mixer.get_volume")

    async def set_hardware_duty(self, val: int):
        """Set volume duty."""
        await self.client.rpc("core.mixer.set_volume", val)


async def queue_playlist(rpc: MopidyRPC, name: str):
    """Queue a given playlist by name."""
    playlists = await rpc.rpc("core.playlists.as_list")
    assert playlists
    playlist = next(x["uri"] for x in playlists if x["name"] == name)
    tracks = await rpc.rpc("core.playlists.lookup", playlist)
    uris = [x["uri"] for x in tracks["tracks"]]
    await rpc.rpc("core.tracklist.add", uris=uris)


async def play():
    """Start playback."""
    ATTEMPTS = 4
    for _ in range(ATTEMPTS):
        try:
            rpc = MopidyRPC()
            await rpc.rpc("core.tracklist.clear")
            await queue_playlist(rpc, "alarm")
            await rpc.rpc("core.tracklist.shuffle")
            await rpc.rpc("core.playback.play")
        except Exception:
            logger.exception("Failed to start playback")
        else:
            return


async def stop():
    """Stop playback."""
    rpc = MopidyRPC()
    await rpc.rpc("core.playback.stop")


mopidy_volume = MopidyVolume(host="localhost", max_fade_freq_hz=4)
