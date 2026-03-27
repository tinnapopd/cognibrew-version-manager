import time
from typing import Optional

import docker
from docker.errors import APIError
from docker.models.containers import Container

from core.logger import Logger
from core.config import settings

logger = Logger().get_logger()


docker_client = docker.from_env()


def _find_containers() -> list[Container]:
    containers = docker_client.containers.list(
        filters={"label": settings.docker.TARGET_LABEL}
    )
    if not containers:
        raise APIError("No running containers found with target label")
    return containers


def _read_threshold(container: Container) -> float:
    env_list = container.attrs["Config"]["Env"]
    for entry in env_list:
        if entry.startswith("MODEL_SIMILARITY_THRESHOLD="):
            return float(entry.split("=", 1)[1])

    raise APIError(
        f"MODEL_SIMILARITY_THRESHOLD not found in "
        f"container '{container.name}' environment"
    )


def _wait_healthy(container: Container, timeout: Optional[int] = None) -> bool:
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


def apply_threshold(threshold: float) -> None:
    containers = _find_containers()
    for old in containers:
        current = _read_threshold(old)
        if abs(current - threshold) < 1e-2:
            # If threshold is already set (difference within 0.01), skip
            continue

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

            replacement = docker_client.containers.run(**run_kwargs)

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
                docker_client.containers.get(new_name).remove(force=True)
            except Exception:
                pass
