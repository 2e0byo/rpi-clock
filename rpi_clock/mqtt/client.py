from aiomqtt import Client

from rpi_clock.config import Settings


def connect() -> Client:
    settings = Settings()
    return Client(
        settings.mqtt_host,
        username=settings.mqtt_user,
        password=settings.mqtt_pass,
        port=settings.mqtt_port,
    )
