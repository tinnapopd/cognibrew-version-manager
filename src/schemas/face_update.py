from typing import Literal

from pydantic import BaseModel, Field


class FaceUpdateRequest(BaseModel):
    person_id: str = Field(
        ..., description="Unique ID (used as Qdrant point ID)"
    )
    username: str = Field(..., description="Display name / label")
    embedding: list[float] = Field(
        default_factory=list,
        description="Face embedding vector (e.g. 512-dim)",
    )
    action: Literal["CREATE", "UPDATE", "DELETE"] = Field(
        ..., description="Operation to perform"
    )


class MessageResponse(BaseModel):
    status: str
    detail: str
