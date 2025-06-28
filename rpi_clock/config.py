from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = "DEBUG"
    mqtt_user: str
    mqtt_pass: str
    mqtt_host: str
    mqtt_port: int = 1883
