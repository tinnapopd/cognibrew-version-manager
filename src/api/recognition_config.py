"""Config management endpoints - rolling container update."""

import time

import docker
from docker.errors import APIError
from docker.models.containers import Container
from fastapi import APIRouter, HTTPException

from schemas import ContainerThreshold, ThresholdResponse, ThresholdUpdate
from schemas.face_update import MessageResponse
from core.config import settings
from core.logger import Logger

logger = Logger().get_logger()

router = APIRouter(prefix="/config", tags=["config"])

# Lazy initialization
_docker_client: docker.DockerClient | None = None


def _get_docker() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _find_containers() -> list[Container]:
    """Discover all running containers that match the target label."""
    client = _get_docker()
    containers = client.containers.list(
        filters={"label": settings.docker.TARGET_LABEL}
    )
    if not containers:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No running containers found with "
                f"label '{settings.docker.TARGET_LABEL}'"
            ),
        )
    return containers


def _read_threshold(container: Container) -> float:
    """Extract MODEL_SIMILARITY_THRESHOLD from a container's env."""
    env_list: list[str] = container.attrs["Config"]["Env"]
    for entry in env_list:
        if entry.startswith("MODEL_SIMILARITY_THRESHOLD="):
            return float(entry.split("=", 1)[1])
    raise HTTPException(
        status_code=500,
        detail=(
            f"MODEL_SIMILARITY_THRESHOLD not found in "
            f"container '{container.name}' environment"
        ),
    )


def _wait_healthy(
    container: Container,
    timeout: int | None = None,
) -> bool:
    """Poll until the container reports *healthy* or timeout expires.

    If the image has no HEALTHCHECK, fall back to checking that the
    container state is 'running' after a brief grace period.
    """
    if timeout is None:
        timeout = settings.docker.HEALTH_TIMEOUT_S

    for _ in range(timeout):
        container.reload()
        health = container.attrs["State"].get("Health")

        if health is not None:
            if health["Status"] == "healthy":
                return True
            if health["Status"] == "unhealthy":
                return False
        else:
            if container.status == "running":
                time.sleep(2)
                container.reload()
                return container.status == "running"

        time.sleep(settings.docker.HEALTH_POLL_S)

    return False


@router.get("/threshold", response_model=ThresholdResponse)
def get_threshold() -> ThresholdResponse:
    """Read MODEL_SIMILARITY_THRESHOLD from all matching containers."""
    containers = _find_containers()
    results = []
    for c in containers:
        results.append(
            ContainerThreshold(
                container=c.name or "",
                threshold=_read_threshold(c),
            )
        )
    return ThresholdResponse(containers=results)


@router.put("/threshold", response_model=MessageResponse)
def update_threshold(body: ThresholdUpdate) -> MessageResponse:
    """Rolling update of MODEL_SIMILARITY_THRESHOLD.

    For each matching container:
    1. Start a replacement with the new env var.
    2. Wait for it to pass its health check.
    3. Stop & remove the old container.
    4. Rename the replacement → original name.

    If any container fails its health check the rollout stops and
    the response reports which containers were updated successfully.
    """
    containers = _find_containers()
    updated: list[str] = []

    for old in containers:
        old_name = old.name or ""
        new_name = f"{old_name}-new"

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
            new_env.append(f"MODEL_SIMILARITY_THRESHOLD={body.threshold}")

            run_kwargs: dict = {
                "image": image,
                "name": new_name,
                "environment": new_env,
                "labels": old_labels,
                "detach": True,
            }
            if network_name:
                run_kwargs["network"] = network_name

            logger.info(
                "rolling_update_starting",
                extra={"old": old_name, "new": new_name, "image": image},
            )
            replacement = _get_docker().containers.run(**run_kwargs)

            if not _wait_healthy(replacement):
                replacement.stop()
                replacement.remove()
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Replacement '{new_name}' failed health check. "
                        f"Rolling update stopped. "
                        f"Updated so far: {updated}"
                    ),
                )

            old.stop(timeout=10)
            old.remove()
            replacement.rename(old_name)
            updated.append(old_name)

            logger.info(
                "rolling_update_container_done",
                extra={
                    "container": old_name,
                    "new_id": replacement.short_id,
                    "threshold": body.threshold,
                },
            )

        except HTTPException:
            raise
        except APIError as exc:
            logger.error(
                "rolling_update_error",
                extra={"error": str(exc), "container": old_name},
            )
            try:
                _get_docker().containers.get(new_name).remove(force=True)
            except Exception:
                pass
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Docker API error on '{old_name}': {exc}. "
                    f"Updated so far: {updated}"
                ),
            )

    return MessageResponse(
        status="ok",
        detail=(
            f"Rolling update complete. "
            f"{len(updated)} container(s) updated to "
            f"MODEL_SIMILARITY_THRESHOLD={body.threshold}"
        ),
    )
