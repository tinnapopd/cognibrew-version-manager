"""Tests for the sync API endpoints."""

from unittest.mock import AsyncMock


class TestGetSyncStatus:
    """GET /sync/status."""

    def test_returns_default_status(self, test_client):
        resp = test_client.get("/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_version"] == 0
        assert data["last_pull_at"] is None


class TestTriggerSync:
    """POST /sync/trigger."""

    def test_trigger_calls_pull_bundle(self, test_client):
        import core.sync_client as sc_mod

        original = sc_mod.pull_bundle
        mock_pull = AsyncMock()
        sc_mod.pull_bundle = mock_pull
        try:
            resp = test_client.post("/sync/trigger")
            assert resp.status_code == 200
            mock_pull.assert_called_once()
        finally:
            sc_mod.pull_bundle = original

    def test_trigger_skips_when_already_running(self, test_client):
        import core.sync_client as sc_mod

        original = sc_mod.pull_bundle
        mock_pull = AsyncMock()
        sc_mod.pull_bundle = mock_pull
        sc_mod.sync_state.is_running = True
        try:
            resp = test_client.post("/sync/trigger")
            assert resp.status_code == 200
            mock_pull.assert_not_called()
        finally:
            sc_mod.pull_bundle = original
            sc_mod.sync_state.is_running = False
