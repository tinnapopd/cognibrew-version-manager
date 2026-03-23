"""Sync endpoints — status & manual trigger."""

from __future__ import annotations

from fastapi import APIRouter

import core.sync_client as sync_client_mod
from core.config import settings
from schemas.sync import SyncStatusResponse

router = APIRouter(prefix="/sync", tags=["sync"])


def _build_status() -> SyncStatusResponse:
    state = sync_client_mod.sync_state
    return SyncStatusResponse(
        enabled=settings.sync.ENABLED,
        current_version=state.current_version,
        last_pull_at=state.last_pull_at,
        last_pull_version=state.last_pull_version,
        last_pull_threshold=state.last_pull_threshold,
        last_pull_users_synced=state.last_pull_users_synced,
    )


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status() -> SyncStatusResponse:
    """Return the current edge-pull sync state."""
    return _build_status()


@router.post("/trigger", response_model=SyncStatusResponse)
async def trigger_sync() -> SyncStatusResponse:
    """Manually trigger an immediate sync pull."""
    if sync_client_mod.sync_state.is_running:
        return _build_status()

    await sync_client_mod.pull_bundle()

    return _build_status()
