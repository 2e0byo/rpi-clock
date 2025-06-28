import asyncio
import json
from datetime import datetime

from structlog import get_logger

from rpi_clock import clock, hal
from rpi_clock.mopidy import mopidy_volume
from rpi_clock.mqtt.publish import CONFIG

from .client import connect

logger = get_logger()


class FadeableHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic

    async def state(self) -> int:
        return int(await self.thing.get_percent_duty() * 255)

    async def handle(self, msg: str | int | float):
        try:
            data = json.loads(msg)
            val = (
                data["brightness"]
                if "brightness" in data
                else {"ON": 255, "OFF": 0}[data["state"]]
            )
            asyncio.create_task(
                self.thing.fade(
                    percent_duty=val / 255, duration=data.get("transition", 1)
                )
            )
        except (json.JSONDecodeError, TypeError):
            val = int(msg) / 255
            await self.thing.set_percent_duty(val)

    async def subscribe(self):
        async with connect() as client:
            await client.subscribe(self.state_topic)
            await client.publish(self.state_topic, await self.state())
            async for msg in client.messages:
                try:
                    assert msg.payload
                    assert not isinstance(msg.payload, bytearray)
                    assert not isinstance(msg.payload, bytes)
                    await self.handle(msg.payload)
                except Exception:
                    logger.exception(
                        "Failed to handle message for %s", self.cmd_topic, msg=msg
                    )
                finally:
                    await client.publish(self.state_topic, await self.state())


class SwitchHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic

    def state(self) -> str:
        return "ON" if self.thing.value else "OFF"

    async def handle(self, msg: str):
        if msg == "ON":
            self.thing.value = True
        elif msg == "OFF":
            self.thing.value = False
        else:
            raise ValueError(msg)

    async def subscribe(self):
        async with connect() as client:
            await client.subscribe(self.state_topic)
            await client.publish(self.state_topic, self.state())
            async for msg in client.messages:
                try:
                    assert msg.payload
                    assert isinstance(msg.payload, str)
                    await self.handle(msg.payload)
                except Exception:
                    logger.exception(
                        "Failed to handle message for %s", self.cmd_topic, msg=msg
                    )
                finally:
                    await client.publish(self.state_topic, self.state())


lamp = FadeableHandler(
    hal.lamp,
    CONFIG["lamp"].payload["command_topic"],
    CONFIG["lamp"].payload["brightness_state_topic"],
)
hw_volume = FadeableHandler(
    hal.volume,
    CONFIG["hw-volume"].payload["command_topic"],
    CONFIG["hw-volume"].payload["state_topic"],
)
sw_volume = FadeableHandler(
    mopidy_volume,
    CONFIG["sw-volume"].payload["command_topic"],
    CONFIG["sw-volume"].payload["state_topic"],
)
mute = SwitchHandler(
    hal.mute,
    CONFIG["mute"].payload["command_topic"],
    CONFIG["mute"].payload["state_topic"],
)


async def handle_alarm():
    cmd_topic = CONFIG["alarm-time"].payload["command_topic"]
    state_topic = CONFIG["alarm-time"].payload["state_topic"]

    async with connect() as client:
        await client.subscribe(cmd_topic)
        if target := clock.alarm.target:
            await client.publish(state_topic, target.strftime("%H:%M"))
        async for msg in client.messages:
            try:
                assert msg.payload
                assert isinstance(msg.payload, str)
                time = datetime.strptime(msg.payload, "%H:%M").time()
                clock.alarm.target = time
            except Exception:
                logger.exception("Failed to handle message for %s", cmd_topic, msg=msg)
            finally:
                if target := clock.alarm.target:
                    await client.publish(state_topic, target.strftime("%H:%M"))


async def handle_alarm_enabled():
    cmd_topic = CONFIG["alarm-enabled"].payload["command_topic"]
    state_topic = CONFIG["alarm-enabled"].payload["state_topic"]

    async with connect() as client:
        await client.subscribe(cmd_topic)
        await client.publish(state_topic, "ON" if clock.alarm.enabled else "OFF")
        async for msg in client.messages:
            try:
                assert msg.payload
                assert isinstance(msg.payload, str)
                clock.alarm.enabled = True if msg.payload == "ON" else False
            except Exception:
                logger.exception("Failed to handle message for %s", cmd_topic, msg=msg)
            finally:
                await client.publish(
                    state_topic, "ON" if clock.alarm.enabled else "OFF"
                )


async def handle_alarm_trigger():
    cmd_topic = CONFIG["alarm-trigger"].payload["command_topic"]

    async with connect() as client:
        await client.subscribe(cmd_topic)
        async for msg in client.messages:
            try:
                assert msg.payload == "PRESS"
                clock.alarm.trigger()
            except Exception:
                logger.exception("Failed to handle message for %s", cmd_topic, msg=msg)


async def handle_alarm_cancel():
    cmd_topic = CONFIG["alarm-cancel"].payload["command_topic"]

    async with connect() as client:
        await client.subscribe(cmd_topic)
        async for msg in client.messages:
            try:
                assert msg.payload == "PRESS"
                clock.alarm.cancel()
            except Exception:
                logger.exception("Failed to handle message for %s", cmd_topic, msg=msg)


async def setup_mqtt():
    from . import publish

    logger.info("publishing")

    await publish.publish()
    logger.info("Setting up mqtt handlers")

    asyncio.create_task(lamp.subscribe())
    asyncio.create_task(hw_volume.subscribe())
    asyncio.create_task(sw_volume.subscribe())
    asyncio.create_task(mute.subscribe())

    asyncio.create_task(handle_alarm())
    asyncio.create_task(handle_alarm_enabled())
    asyncio.create_task(handle_alarm_trigger())
    asyncio.create_task(handle_alarm_cancel())
