from typing import NamedTuple

PREFIX = "homeassistant"
ID = "sunrise_clock"


class Config(NamedTuple):
    discovery_topic: str
    payload: dict


CONFIG = {
    "lamp": Config(
        f"{PREFIX}/light/{ID}_lamp_brightness/config",
        {
            "name": "Sunrise Clock Lamp Brightness",
            "unique_id": "sunrise_clock_lamp_brightness",
            "brightness_state_topic": "sunrise_clock/lamp/brightness/state",
            "brightness_command_topic": "sunrise_clock/lamp/target_fade",
            "command_topic": "sunrise_clock/lamp/set",
            "brightness": True,
            "schema": "json",
            "retain": True,
        },
    ),
    "mute": Config(
        f"{PREFIX}/switch/{ID}_mute/config",
        {
            "name": "Sunrise Clock Mute",
            "unique_id": "sunrise_clock_mute",
            "state_topic": "sunrise_clock/mute/state",
            "command_topic": "sunrise_clock/mute/set",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:volume-variant-off",
            "retain": True,
        },
    ),
    "hw-volume": Config(
        f"{PREFIX}/number/{ID}_hw_volume/config",
        {
            "name": "Sunrise Clock Hardware Volume",
            "unique_id": "sunrise_clock_hw_volume",
            "state_topic": "sunrise_clock/hw_volume/state",
            "command_topic": "sunrise_clock/hw_volume/target_fade",
            "unit_of_measurement": "%",
            "min": 0,
            "max": 100,
            "mode": "slider",
            "icon": "mdi:volume-high",
            "retain": True,
        },
    ),
    "sw-volume": Config(
        f"{PREFIX}/number/{ID}_sw_volume/config",
        {
            "name": "Sunrise Clock Software Volume",
            "unique_id": "sunrise_clock_sw_volume",
            "state_topic": "sunrise_clock/sw_volume/state",
            "command_topic": "sunrise_clock/sw_volume/target_fade",
            "unit_of_measurement": "%",
            "min": 0,
            "max": 100,
            "mode": "slider",
            "icon": "mdi:volume-high",
            "retain": True,
        },
    ),
    "alarm-time": Config(
        f"{PREFIX}/text/{ID}_alarm_time/config",
        {
            "name": "Sunrise Clock Alarm Time",
            "unique_id": "sunrise_clock_alarm_time",
            "state_topic": "sunrise_clock/alarm/time/state",
            "command_topic": "sunrise_clock/alarm/time/set",
            "value_template": "{ value }",
            "retain": True,
        },
    ),
    "alarm-enabled": Config(
        f"{PREFIX}/switch/{ID}_alarm_enabled/config",
        {
            "name": "Sunrise Clock Alarm Enabled",
            "unique_id": "sunrise_clock_alarm_enabled",
            "state_topic": "sunrise_clock/alarm/enabled/state",
            "command_topic": "sunrise_clock/alarm/enabled/set",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:bell",
            "retain": True,
        },
    ),
    "alarm-trigger": Config(
        f"{PREFIX}/button/{ID}_alarm_trigger/config",
        {
            "name": "Sunrise Clock Alarm Trigger",
            "unique_id": "sunrise_clock_alarm_trigger",
            "command_topic": "sunrise_clock/alarm/trigger/set",
            "icon": "mdi:bell-alert-outline",
        },
    ),
    "alarm-cancel": Config(
        f"{PREFIX}/button/{ID}_alarm_cancel/config",
        {
            "name": "Sunrise Clock Alarm Cancel",
            "unique_id": "sunrise_clock_alarm_cancel",
            "command_topic": "sunrise_clock/alarm/cancel/set",
            "icon": "mdi:bell-off-outline",
        },
    ),
}


async def publish():
    import json

    from structlog import get_logger

    from .client import connect

    logger = get_logger()

    async with connect() as client:
        for name, config in CONFIG.items():
            logger.info("Publishing %s", name, config=config)
            await client.publish(config.discovery_topic, json.dumps(config.payload))
