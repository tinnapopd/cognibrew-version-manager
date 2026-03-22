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


class Settings:
    """Main configuration class aggregating all settings."""

    def __init__(self) -> None:
        self.rabbitmq = RabbitMQConfig()


# Module-level singleton instance
settings = Settings()
