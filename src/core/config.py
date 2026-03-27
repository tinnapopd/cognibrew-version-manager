import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQConfig(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_prefix="RABBITMQ_",
        case_sensitive=False,
    )

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=5672)
    USERNAME: str = Field(default="guest")
    PASSWORD: str = Field(default="guest")

    # Face update (cloud --> vectordb)
    FACE_UPDATE_EXCHANGE_NAME: str = Field(default="cognibrew.vectordb")
    FACE_UPDATE_QUEUE_NAME: str = Field(
        default="cognibrew.vectordb.face_updated"
    )
    FACE_UPDATE_ROUTING_KEY: str = Field(default="face.updated")


class DockerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_prefix="DOCKER_",
        case_sensitive=False,
    )

    TARGET_LABEL: str = Field(default="cognibrew.service=recognition")
    HEALTH_TIMEOUT_S: int = Field(default=30)
    HEALTH_POLL_S: int = Field(default=1)


class SyncConfig(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_prefix="SYNC_",
        case_sensitive=False,
    )

    URL: str = Field(default="http://edge-sync.melierx.com/api/v1/sync/bundle")
    DEVICE_ID: str = Field(default_factory=lambda: SyncConfig._get_mac())
    PAGE_SIZE: int = Field(default=50)
    SCHEDULE_TIME: str = Field(default="01:00")
    CHECK_EVERY: int = Field(default=60)  # seconds

    @staticmethod
    def _get_mac() -> str:
        mac = uuid.getnode()
        return ":".join(
            f"{(mac >> (8 * i)) & 0xFF:02x}" for i in range(5, -1, -1)
        ).replace(":", "-")


class Settings:
    """Main configuration class aggregating all settings."""

    def __init__(self) -> None:
        self.rabbitmq = RabbitMQConfig()
        self.docker = DockerConfig()
        self.sync = SyncConfig()


# Module-level singleton instance
settings = Settings()
