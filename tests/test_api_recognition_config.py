from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.recognition_config import _read_threshold, _wait_healthy


def _make_container(
    name: str = "svc-1",
    env: list[str] | None = None,
    health_status: str | None = "healthy",
    status: str = "running",
    image: str = "img:latest",
    labels: dict | None = None,
    network: str = "bridge",
) -> MagicMock:
    """Build a mock Docker container with sensible defaults."""
    c = MagicMock()
    c.name = name
    c.status = status
    c.short_id = "abc123"

    if env is None:
        env = [
            "FOO=bar",
            "MODEL_SIMILARITY_THRESHOLD=0.8",
        ]

    health = {"Status": health_status} if health_status else None
    c.attrs = {
        "Config": {
            "Image": image,
            "Env": env,
            "Labels": labels or {},
        },
        "State": {"Health": health},
        "NetworkSettings": {"Networks": {network: {}}},
    }
    c.reload = MagicMock()
    return c


class TestReadThreshold:
    def test_reads_value(self):
        c = _make_container(env=["MODEL_SIMILARITY_THRESHOLD=0.72"])
        assert _read_threshold(c) == pytest.approx(0.72)

    def test_missing_var_raises_500(self):
        c = _make_container(env=["OTHER=1"])
        with pytest.raises(HTTPException) as exc_info:
            _read_threshold(c)
        err = exc_info.value
        assert isinstance(err, HTTPException)
        assert err.status_code == 500


class TestWaitHealthy:
    def test_returns_true_when_healthy(self):
        c = _make_container(health_status="healthy")
        assert _wait_healthy(c, timeout=3) is True

    def test_returns_false_when_unhealthy(self):
        c = _make_container(health_status="unhealthy")
        assert _wait_healthy(c, timeout=3) is False

    @patch("api.recognition_config.time.sleep")
    def test_no_healthcheck_falls_back_to_running(self, mock_sleep):
        c = _make_container(health_status=None, status="running")
        # After reload the container is still running
        c.reload = MagicMock()
        assert _wait_healthy(c, timeout=3) is True


class TestGetThreshold:
    def test_success(self, test_client, mock_docker_client):
        containers = [
            _make_container("svc-1", env=["MODEL_SIMILARITY_THRESHOLD=0.8"]),
            _make_container("svc-2", env=["MODEL_SIMILARITY_THRESHOLD=0.9"]),
        ]
        mock_docker_client.containers.list.return_value = containers

        resp = test_client.get("/config/threshold")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["containers"]) == 2
        assert data["containers"][0]["threshold"] == pytest.approx(0.8)

    def test_no_containers_returns_404(self, test_client, mock_docker_client):
        mock_docker_client.containers.list.return_value = []

        resp = test_client.get("/config/threshold")
        assert resp.status_code == 404


class TestUpdateThreshold:
    @patch("api.recognition_config._wait_healthy", return_value=True)
    def test_rolling_update_success(
        self, mock_wait, test_client, mock_docker_client
    ):
        old = _make_container("svc-1")
        replacement = _make_container("svc-1-new")
        mock_docker_client.containers.list.return_value = [old]
        mock_docker_client.containers.run.return_value = replacement

        resp = test_client.put("/config/threshold", json={"threshold": 0.75})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "1 container(s) updated" in body["detail"]

        old.stop.assert_called_once()
        old.remove.assert_called_once()
        replacement.rename.assert_called_once_with("svc-1")

    @patch("api.recognition_config._wait_healthy", return_value=False)
    def test_health_check_failure_returns_502(
        self, mock_wait, test_client, mock_docker_client
    ):
        old = _make_container("svc-1")
        replacement = _make_container("svc-1-new")
        mock_docker_client.containers.list.return_value = [old]
        mock_docker_client.containers.run.return_value = replacement

        resp = test_client.put("/config/threshold", json={"threshold": 0.75})
        assert resp.status_code == 502

        replacement.stop.assert_called_once()
        replacement.remove.assert_called_once()

    def test_invalid_threshold_returns_422(
        self, test_client, mock_docker_client
    ):
        resp = test_client.put("/config/threshold", json={"threshold": 0.0})
        assert resp.status_code == 422
