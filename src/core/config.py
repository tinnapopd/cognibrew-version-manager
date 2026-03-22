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


class Settings:
    """Main configuration class aggregating all settings."""

    def __init__(self) -> None:
        self.rabbitmq = RabbitMQConfig()
        self.docker = DockerConfig()


# Module-level singleton instance
settings = Settings()
