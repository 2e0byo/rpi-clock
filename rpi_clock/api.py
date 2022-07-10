"""An api to control the clock."""
import asyncio
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from gpiozero import LED

from . import clock, hal
from .alarm import AlarmEndpoint
from .endpoint import Endpoint
from .fadeable import FadeableEndpoint
from .mopidy import mopidy_volume

app = FastAPI()


class PinEndpoint(Endpoint[LED]):
    """An endpoint to control a pin."""

    def __init__(self, *args, **kwargs):
        """Initialise a new pin endpoint."""
        super().__init__(*args, **kwargs)
        self.router.get("/")(self.get_state)
        self.router.put("/")(self.set_state)

    def get_state(self):
        """Get current pin state."""
        return {"value": bool(self.pin.value)}

    def set_state(self, state: bool):
        """Set the pin state."""
        self.pin.value = state
        return self.get_state()


lamp = FadeableEndpoint(thing=hal.lamp, prefix="/lamp")
volume = FadeableEndpoint(thing=hal.volume, prefix="/volume")
mopidy_volume = FadeableEndpoint(thing=mopidy_volume, prefix="/mopidy-volume")
backlight = FadeableEndpoint(thing=hal.backlight, prefix="/backlight")
mute = PinEndpoint(thing=hal.mute, prefix="/mute")

alarm = AlarmEndpoint(thing=clock.alarm, prefix="/alarm")

app.include_router(lamp.router)
app.include_router(volume.router)
app.include_router(mopidy_volume.router)
app.include_router(backlight.router)
app.include_router(mute.router)
app.include_router(alarm.router)


@app.get("/")
def root():
    """Root page."""
    return RedirectResponse("/docs")
