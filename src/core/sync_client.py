import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from core.config import settings
from core.logger import Logger
from schemas.sync import SyncBundleResponse

logger = Logger().get_logger()


@dataclass
class SyncState:
    """Mutable state tracked across pull cycles."""

    current_version: int = 0
    last_pull_at: str | None = None
    last_pull_version: int | None = None
    last_pull_threshold: float | None = None
    last_pull_users_synced: int | None = None
    is_running: bool = False


# Module-level singleton
sync_state: SyncState = SyncState()


async def pull_bundle() -> None:
    """Pull the latest bundle from cloud-edge-sync and apply it.

    Pagination: keeps fetching pages while ``has_more`` is True.
    """
    _state = sync_state  # local alias for Pyrefly
    cfg = settings.sync
    base_url = f"{cfg.CLOUD_URL}/api/v1/sync/bundle"

    total_users_synced = 0
    version: int | None = None
    threshold: float | None = None

    _state.is_running = True
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            offset = 0
            while True:
                params = {
                    "current_version": _state.current_version,
                    "offset": offset,
                    "limit": cfg.PAGE_SIZE,
                }
                logger.info(
                    "sync_pull_page",
                    extra={"url": base_url, "params": params},
                )

                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
                bundle = SyncBundleResponse.model_validate(resp.json())

                version = bundle.version
                threshold = bundle.threshold

                # No update available
                if bundle.users_synced == 0 and not bundle.gallery:
                    logger.info(
                        "sync_no_update",
                        extra={
                            "cloud_version": version,
                            "edge_version": _state.current_version,
                        },
                    )
                    break

                # Apply threshold via Docker rolling-update
                if threshold is not None:
                    await _apply_threshold(threshold)

                # Apply gallery via RabbitMQ face-update pipeline
                if bundle.gallery:
                    await _apply_gallery(bundle.gallery)

                total_users_synced += bundle.users_synced

                if not bundle.has_more:
                    break
                offset += cfg.PAGE_SIZE

        # Update state after successful pull
        if version is not None:
            _state.current_version = version

        _state.last_pull_at = datetime.now(timezone.utc).isoformat()
        _state.last_pull_version = version
        _state.last_pull_threshold = threshold
        _state.last_pull_users_synced = total_users_synced

        logger.info(
            "sync_pull_complete",
            extra={
                "version": version,
                "threshold": threshold,
                "users_synced": total_users_synced,
            },
        )

    except Exception:
        logger.exception("sync_pull_failed")
    finally:
        _state.is_running = False


async def _apply_threshold(threshold: float) -> None:
    """Rolling-update threshold on recognition containers."""
    from api.recognition_config import (
        _find_containers,
        _get_docker,
        _read_threshold,
        _wait_healthy,
    )

    logger.info("sync_apply_threshold", extra={"threshold": threshold})

    try:
        containers = _find_containers()
    except Exception:
        logger.warning("sync_no_containers_found, skipping threshold update")
        return

    for old in containers:
        current = _read_threshold(old)
        if abs(current - threshold) < 1e-9:
            continue  # already at target

        old_name = old.name or ""
        new_name = f"{old_name}-sync"
        try:
            old_attrs = old.attrs
            image = old_attrs["Config"]["Image"]
            old_env = old_attrs["Config"]["Env"]
            old_labels = old_attrs["Config"].get("Labels", {})
            networking = old_attrs.get("NetworkSettings", {})
            network_name = next(
                iter(networking.get("Networks", {}).keys()), None
            )

            new_env = [
                e
                for e in old_env
                if not e.startswith("MODEL_SIMILARITY_THRESHOLD=")
            ]
            new_env.append(f"MODEL_SIMILARITY_THRESHOLD={threshold}")

            run_kwargs: dict = {
                "image": image,
                "name": new_name,
                "environment": new_env,
                "labels": old_labels,
                "detach": True,
            }
            if network_name:
                run_kwargs["network"] = network_name

            replacement = _get_docker().containers.run(**run_kwargs)

            if not _wait_healthy(replacement):
                replacement.stop()
                replacement.remove()
                logger.error(
                    "sync_threshold_health_failed",
                    extra={"container": old_name},
                )
                continue

            old.stop(timeout=10)
            old.remove()
            replacement.rename(old_name)

            logger.info(
                "sync_threshold_updated",
                extra={"container": old_name, "threshold": threshold},
            )
        except Exception:
            logger.exception(
                "sync_threshold_error",
                extra={"container": old_name},
            )
            try:
                _get_docker().containers.get(new_name).remove(force=True)
            except Exception:
                pass


async def _apply_gallery(
    gallery: dict[str, list[list[float]]],
) -> None:
    """Publish gallery embeddings to RabbitMQ as UPDATE face-update events."""
    from api.face_update import _get_mq
    from schemas.proto.face_update_pb2 import PersonUpdate  # type: ignore

    logger.info("sync_apply_gallery", extra={"users": len(gallery)})

    mq = _get_mq()
    for username, embeddings in gallery.items():
        for i, embedding in enumerate(embeddings):
            msg = PersonUpdate(
                person_id=f"{username}-sync-{i}",
                username=username,
                embedding=embedding,
                action=PersonUpdate.UPDATE,
            )
            mq.publish(
                body=msg.SerializeToString(),
                routing_key=settings.rabbitmq.FACE_UPDATE_ROUTING_KEY,
            )

    logger.info(
        "sync_gallery_published",
        extra={
            "users": len(gallery),
            "total_vectors": sum(len(v) for v in gallery.values()),
        },
    )


async def start_sync_loop() -> None:
    """Background loop that pulls from cloud at the configured interval."""
    cfg = settings.sync
    if not cfg.ENABLED:
        logger.info("sync_disabled — background loop will not start")
        return

    logger.info(
        "sync_loop_started",
        extra={"interval_hours": cfg.INTERVAL_HOURS},
    )

    while True:
        await pull_bundle()
        await asyncio.sleep(cfg.INTERVAL_HOURS * 3600)
