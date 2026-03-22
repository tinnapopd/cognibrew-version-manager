"""Shared fixtures for the cognibrew-version-manager test suite."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def test_client():
    """FastAPI TestClient with lazy singletons reset after each test."""
    import api.face_update as fu_mod
    import api.recognition_config as rc_mod
    from main import app

    # Reset lazy singletons so each test starts clean
    fu_mod._mq = None
    rc_mod._docker_client = None

    with TestClient(app) as client:
        yield client

    fu_mod._mq = None
    rc_mod._docker_client = None


@pytest.fixture()
def mock_mq():
    """Patch the face-update module's lazy MQ singleton with a MagicMock."""
    import api.face_update as fu_mod

    mq = MagicMock()
    fu_mod._mq = mq
    yield mq
    fu_mod._mq = None


@pytest.fixture()
def mock_docker_client():
    """Patch the recognition-config module's Docker client."""
    import api.recognition_config as rc_mod

    client = MagicMock()
    rc_mod._docker_client = client
    yield client
    rc_mod._docker_client = None
