import asyncio
import json
from datetime import datetime
from time import perf_counter

from structlog import get_logger

from rpi_clock import clock, hal
from rpi_clock.alarm import Alarm
from rpi_clock.mopidy import mopidy_volume
from rpi_clock.mqtt.publish import CONFIG

from .client import connect

logger = get_logger()


class FadeableHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic
        self._state = None

    async def state(self) -> int:
        assert self._state is not None
        return self._state

    async def init(self, val: str):
        self._state = int(val)
        await self.thing.fade(val / 255, duration=1)

    async def hardware_init(self):
        val = await self.thing.get_percent_duty()
        self._state = round(val * 255)

    async def handle(self, msg: str):
        data = json.loads(msg)
        assert isinstance(data, dict), repr(data)
        if data["state"] == "ON":
            brightness = data.get("brightness", self._state)
            self._state = brightness
        else:
            brightness = 0
        asyncio.create_task(
            self.thing.fade(
                percent_duty=brightness / 255, duration=data.get("transition", 1)
            )
        )


class SwitchHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic

    async def hardware_init(self):
        pass

    async def state(self) -> str:
        return "ON" if self.thing.value else "OFF"

    async def handle(self, msg: str):
        if msg == "ON":
            self.thing.value = True
        elif msg == "OFF":
            self.thing.value = False
        else:
            raise ValueError(msg)

    init = handle


class AlarmTimeHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing: Alarm = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic

    async def hardware_init(self):
        pass

    async def state(self) -> str | None:
        if target := self.thing.target:
            return target.strftime("%H:%M")

    async def handle(self, msg: str):
        self.thing.target = datetime.strptime(msg, "%H:%M").time()

    init = handle


class AlarmEnabledHandler:
    def __init__(self, thing, cmd_topic: str, state_topic: str):
        self.thing: Alarm = thing
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic

    async def hardware_init(self):
        pass

    async def state(self) -> str:
        return "ON" if self.thing.enabled else "OFF"

    async def handle(self, msg: str):
        self.thing.enabled = True if msg == "ON" else False

    init = handle


class AlarmTriggerHandler:
    def __init__(self, thing, cmd_topic: str):
        self.thing: Alarm = thing
        self.cmd_topic = cmd_topic

    async def state(self) -> None:
        return None

    async def handle(self, msg: str):
        assert msg == "PRESS"
        self.thing.trigger()


class AlarmCancelHandler:
    def __init__(self, thing, cmd_topic: str):
        self.thing: Alarm = thing
        self.cmd_topic = cmd_topic

    async def state(self) -> None:
        return None

    async def handle(self, msg: str):
        assert msg == "PRESS"
        self.thing.cancel()


HANDLERS = dict(
    lamp=FadeableHandler(
        hal.lamp,
        CONFIG["lamp"].payload["command_topic"],
        CONFIG["lamp"].payload["brightness_state_topic"],
    ),
    hw_volume=FadeableHandler(
        hal.volume,
        CONFIG["hw-volume"].payload["command_topic"],
        CONFIG["hw-volume"].payload["state_topic"],
    ),
    sw_volume=FadeableHandler(
        mopidy_volume,
        CONFIG["sw-volume"].payload["command_topic"],
        CONFIG["sw-volume"].payload["state_topic"],
    ),
    mute=SwitchHandler(
        hal.mute,
        CONFIG["mute"].payload["command_topic"],
        CONFIG["mute"].payload["state_topic"],
    ),
    alarm_time=AlarmTimeHandler(
        clock.alarm,
        CONFIG["alarm-time"].payload["command_topic"],
        CONFIG["alarm-time"].payload["state_topic"],
    ),
    alarm_enabled=AlarmEnabledHandler(
        clock.alarm,
        CONFIG["alarm-enabled"].payload["command_topic"],
        CONFIG["alarm-enabled"].payload["state_topic"],
    ),
    alarm_trigger=AlarmTriggerHandler(
        clock.alarm,
        CONFIG["alarm-trigger"].payload["command_topic"],
    ),
    alarm_cancel=AlarmCancelHandler(
        clock.alarm,
        CONFIG["alarm-cancel"].payload["command_topic"],
    ),
)


async def handler():
    cmd_topics = {h.cmd_topic: h for h in HANDLERS.values()}
    async with connect() as client:
        state_topics = {}
        for handler in cmd_topics.values():
            if hasattr(handler, "init"):
                topic = getattr(handler, "state_topic")
                assert topic
                await client.subscribe(topic)
                state_topics[topic] = handler

        logger.info("Receiving any retained state")
        messages = client.messages
        start = perf_counter()
        while perf_counter() - start < 5:
            try:
                async with asyncio.timeout(1):
                    msg = await messages.__anext__()
                    topic = str(msg.topic)
                    handler = state_topics[topic]
                    try:
                        payload = msg.payload
                        if isinstance(payload, bytes):
                            payload = payload.decode()
                        await handler.init(payload)
                    except Exception:
                        logger.exception(
                            "Failed to init %s", handler.state_topic, msg=msg
                        )
                        await handler.hardware_init()
                    finally:
                        await client.unsubscribe(topic)
                        state_topics.pop(topic)
            except asyncio.TimeoutError:
                pass

        for topic, handler in state_topics:
            logger.warn("Got no original state for topic %s", topic)
            await handler.hardware_init()
            await client.unsubscribe(topic)

        for handler in cmd_topics.values():
            await client.subscribe(handler.cmd_topic)

        async for msg in client.messages:
            handler = cmd_topics[str(msg.topic)]
            try:
                payload = msg.payload
                if isinstance(payload, bytes):
                    payload = payload.decode()
                await handler.handle(payload)
            except Exception:
                logger.exception(
                    "Failed to handle message for %s", handler.cmd_topic, msg=msg
                )
            finally:
                if (state := await handler.state()) is not None:
                    logger.info("Publishing updated state %s", handler.state_topic)
                    await client.publish(handler.state_topic, state)


async def setup_mqtt():
    from . import publish

    logger.info("publishing")

    await publish.publish()
    logger.info("Setting up mqtt handlers")
    asyncio.create_task(handler())
