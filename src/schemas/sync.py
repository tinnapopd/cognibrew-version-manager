"""Schemas for the cloud-edge sync feature."""

from pydantic import BaseModel, Field


class SyncBundleResponse(BaseModel):
    """Mirrors the cloud's SyncBundle schema for deserialization."""

    version: int
    threshold: float
    gallery: dict[str, list[list[float]]] = Field(
        default_factory=dict,
        description="Per-user gallery: {username: [[512-dim], ...]}",
    )
    users_synced: int
    has_more: bool = False


class SyncStatusResponse(BaseModel):
    """Status of the edge-pull sync process."""

    enabled: bool
    current_version: int
    last_pull_at: str | None = None
    last_pull_version: int | None = None
    last_pull_threshold: float | None = None
    last_pull_users_synced: int | None = None
    next_pull_in_seconds: int | None = None
