from pydantic import BaseModel, Field


class ContainerThreshold(BaseModel):
    container: str = Field(
        ..., description="Container name"
    )
    threshold: float = Field(
        ..., description="MODEL_SIMILARITY_THRESHOLD value"
    )


class ThresholdResponse(BaseModel):
    containers: list[ContainerThreshold]


class ThresholdUpdate(BaseModel):
    threshold: float = Field(
        ...,
        gt=0,
        le=1,
        description="New similarity threshold (0 < t ≤ 1)",
        examples=[0.75],
    )
