from mopidy_asyncio_client import MopidyClient


async def queue_playlist(mopidy, name: str):
    playlists = await mopidy.playlists.as_list()
    assert playlists
    playlist = next(x["uri"] for x in playlists if x["name"] == name)
    tracks = await mopidy.playlists.lookup(playlist)
    await mopidy.tracklist.add(uris=[x["uri"] for x in tracks["tracks"]])


async def play():
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
    async with MopidyClient(host="localhost") as mopidy:
        await mopidy.playback.stop()
