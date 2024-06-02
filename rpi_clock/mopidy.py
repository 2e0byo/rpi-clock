from mopidy_asyncio_client import MopidyClient

from .fadeable import Fadeable


class MopidyVolume(Fadeable):
    """A volume, fadeable up and down."""

    def __init__(self, *args, host="localhost", **kwargs):
        """Initialise a `MopidyVolume` object."""
        self.client = MopidyClient(host=host)
        self.max_duty = 100
        super().__init__(*args, **kwargs)

    async def get_hardware_duty(self):
        """Get volume duty."""
        async with self.client as mopidy:
            return await mopidy.mixer.get_volume()

    async def set_hardware_duty(self, val: int):
        """Set volume duty."""
        async with self.client as mopidy:
            await mopidy.mixer.set_volume(val)


async def queue_playlist(mopidy, name: str):
    """Queue a given playlist by name."""
    playlists = await mopidy.playlists.as_list()
    assert playlists
    playlist = next(x["uri"] for x in playlists if x["name"] == name)
    tracks = await mopidy.playlists.lookup(playlist)
    await mopidy.tracklist.add(uris=[x["uri"] for x in tracks["tracks"]])


async def play():
    """Start playback."""
    ATTEMPTS = 4
    for _ in range(ATTEMPTS):
        try:
            async with MopidyClient(host="localhost") as mopidy:
                await mopidy.tracklist.clear()
                await queue_playlist(mopidy, "alarm")
                await mopidy.tracklist.shuffle()
                await mopidy.playback.play()
            break
        except Exception:
            continue


async def stop():
    """Stop playback."""
    async with MopidyClient(host="localhost") as mopidy:
        await mopidy.playback.stop()


mopidy_volume = MopidyVolume(host="localhost", max_fade_freq_hz=4)
