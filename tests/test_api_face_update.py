class TestPublishFaceUpdate:
    """POST /face-update/face-update."""

    def test_success(self, test_client, mock_mq):
        payload = {
            "person_id": "p-1",
            "username": "Alice",
            "embedding": [0.1, 0.2],
            "action": "CREATE",
        }
        resp = test_client.post("/face-update/face-update", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "p-1" in body["detail"]
        mock_mq.publish.assert_called_once()

    def test_invalid_action_returns_422(self, test_client, mock_mq):
        payload = {
            "person_id": "p-1",
            "username": "Alice",
            "action": "INVALID",
        }
        resp = test_client.post("/face-update/face-update", json=payload)
        assert resp.status_code == 422

    def test_missing_fields_returns_422(self, test_client, mock_mq):
        resp = test_client.post("/face-update/face-update", json={})
        assert resp.status_code == 422

    def test_publish_error_returns_500(self, test_client, mock_mq):
        mock_mq.publish.side_effect = RuntimeError("connection lost")

        payload = {
            "person_id": "p-1",
            "username": "Alice",
            "embedding": [0.1],
            "action": "DELETE",
        }
        resp = test_client.post("/face-update/face-update", json=payload)

        assert resp.status_code == 500
        assert "connection lost" in resp.json()["detail"]
