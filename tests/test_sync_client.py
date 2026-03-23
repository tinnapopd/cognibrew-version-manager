from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.sync_client import pull_bundle, sync_state


@pytest.fixture(autouse=True)
def _reset_sync_state():
    """Reset module-level sync_state before each test."""
    sync_state.current_version = 0
    sync_state.last_pull_at = None
    sync_state.last_pull_version = None
    sync_state.last_pull_threshold = None
    sync_state.last_pull_users_synced = None
    sync_state.is_running = False
    yield
    sync_state.current_version = 0
    sync_state.last_pull_at = None
    sync_state.last_pull_version = None
    sync_state.last_pull_threshold = None
    sync_state.last_pull_users_synced = None
    sync_state.is_running = False


def _bundle_response(
    version: int = 2,
    threshold: float = 0.75,
    gallery: dict | None = None,
    users_synced: int = 0,
    has_more: bool = False,
) -> dict:
    return {
        "version": version,
        "threshold": threshold,
        "gallery": gallery or {},
        "users_synced": users_synced,
        "has_more": has_more,
    }


class TestPullBundleNoUpdate:
    """Cloud version <= edge version → no update applied."""

    @pytest.mark.asyncio
    async def test_no_update_when_up_to_date(self):
        """When the bundle returns users_synced=0 and empty gallery, skip."""
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json.return_value = _bundle_response(
            version=1, users_synced=0
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = resp_mock
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.sync_client.httpx.AsyncClient", return_value=mock_client
        ):
            await pull_bundle()

        assert sync_state.last_pull_version == 1
        assert sync_state.last_pull_users_synced == 0


class TestPullBundleSinglePage:
    """Single-page bundle with gallery data."""

    @pytest.mark.asyncio
    async def test_applies_threshold_and_gallery(self):
        gallery = {"alice": [[0.1, 0.2]], "bob": [[0.3, 0.4], [0.5, 0.6]]}
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json.return_value = _bundle_response(
            version=3,
            threshold=0.82,
            gallery=gallery,
            users_synced=2,
            has_more=False,
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = resp_mock
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "core.sync_client.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "core.sync_client._apply_threshold", new_callable=AsyncMock
            ) as mock_threshold,
            patch(
                "core.sync_client._apply_gallery", new_callable=AsyncMock
            ) as mock_gallery,
        ):
            await pull_bundle()

        mock_threshold.assert_awaited_once_with(0.82)
        mock_gallery.assert_awaited_once_with(gallery)
        assert sync_state.current_version == 3
        assert sync_state.last_pull_users_synced == 2


class TestPullBundleMultiPage:
    """Multi-page bundle (has_more=True on first page)."""

    @pytest.mark.asyncio
    async def test_fetches_all_pages(self):
        page1 = _bundle_response(
            version=5,
            threshold=0.9,
            gallery={"alice": [[0.1]]},
            users_synced=1,
            has_more=True,
        )
        page2 = _bundle_response(
            version=5,
            threshold=0.9,
            gallery={"bob": [[0.2]]},
            users_synced=1,
            has_more=False,
        )

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.raise_for_status = MagicMock()
        resp1.json.return_value = page1

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.raise_for_status = MagicMock()
        resp2.json.return_value = page2

        mock_client = AsyncMock()
        mock_client.get.side_effect = [resp1, resp2]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "core.sync_client.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("core.sync_client._apply_threshold", new_callable=AsyncMock),
            patch("core.sync_client._apply_gallery", new_callable=AsyncMock),
        ):
            await pull_bundle()

        assert mock_client.get.call_count == 2
        assert sync_state.current_version == 5
        assert sync_state.last_pull_users_synced == 2


class TestPullBundleError:
    """HTTP errors should be caught and logged, not crash."""

    @pytest.mark.asyncio
    async def test_http_error_is_caught(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "503",
            request=MagicMock(),
            response=MagicMock(status_code=503),
        )

        with patch(
            "core.sync_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await pull_bundle()  # should not raise

        # State should not be updated on failure
        assert sync_state.current_version == 0
        assert sync_state.last_pull_version is None
