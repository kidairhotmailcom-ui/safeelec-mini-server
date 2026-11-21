import unittest
from unittest.mock import patch

import main


class FakeResponse:
    status_code = 200
    content = b'{"ok":true,"pending":false}'

    def json(self):
        return {"ok": True, "pending": False}


class JarvisFirmwareBridgeTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        self.token_patch = patch.object(main, "JARVIS_INTEGRATION_TOKEN", "i" * 48)
        self.url_patch = patch.object(main, "JARVIS_CORE_API_URL", "https://jarvis.example")
        self.token_patch.start()
        self.url_patch.start()
        self.addCleanup(self.token_patch.stop)
        self.addCleanup(self.url_patch.stop)

    @patch("main.requests.request", return_value=FakeResponse())
    def test_pending_is_forwarded_with_separate_integration_and_device_credentials(self, request_mock):
        response = self.client.get(
            "/api/jarvis/v1/firmware/pending?device_id=SAFE-001",
            headers={"X-Device-Token": "d" * 48},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "pending": False})
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://jarvis.example/api/jarvis/v1/safe-elec/firmware/device/SAFE-001/pending")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + "i" * 48)
        self.assertEqual(kwargs["headers"]["X-Device-Token"], "d" * 48)

    def test_missing_device_token_is_rejected_before_upstream_request(self):
        response = self.client.get(
            "/api/jarvis/v1/firmware/pending?device_id=SAFE-001"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "INVALID_DEVICE_CREDENTIAL")

    def test_unknown_device_is_rejected(self):
        response = self.client.get(
            "/api/jarvis/v1/firmware/pending?device_id=SAFE-002",
            headers={"X-Device-Token": "d" * 48},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "INVALID_DEVICE_ID")

    def test_claim_requires_update_id(self):
        response = self.client.post(
            "/api/jarvis/v1/firmware/claim",
            json={"device_id": "SAFE-001"},
            headers={"X-Device-Token": "d" * 48},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "INVALID_CLAIM_REQUEST")

    def test_status_rejects_unknown_transition(self):
        response = self.client.post(
            "/api/jarvis/v1/firmware/status",
            json={"device_id": "SAFE-001", "update_id": "u1", "status": "skipped"},
            headers={"X-Device-Token": "d" * 48},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "INVALID_UPDATE_STATUS")

    @patch("main.requests.request", return_value=FakeResponse())
    def test_master_relay_pending_uses_master_credential_and_fixed_backup_target(self, request_mock):
        response = self.client.get(
            "/api/jarvis/v1/firmware/relay/pending",
            headers={"X-Device-Token": "m" * 48},
        )
        self.assertEqual(response.status_code, 200)
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(
            args[1],
            "https://jarvis.example/api/jarvis/v1/safe-elec/firmware/device/SAFE-001/relay/SAFE-001-BAK/pending",
        )
        self.assertEqual(kwargs["headers"]["X-Device-Token"], "m" * 48)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + "i" * 48)

    @patch("main.requests.request", return_value=FakeResponse())
    def test_master_relay_claim_and_status_forward_only_update_fields(self, request_mock):
        claim = self.client.post(
            "/api/jarvis/v1/firmware/relay/claim",
            json={"update_id": "123e4567-e89b-12d3-a456-426614174000"},
            headers={"X-Device-Token": "m" * 48},
        )
        self.assertEqual(claim.status_code, 200)
        self.assertEqual(request_mock.call_args.kwargs["json"], {
            "update_id": "123e4567-e89b-12d3-a456-426614174000"
        })
        status = self.client.post(
            "/api/jarvis/v1/firmware/relay/status",
            json={
                "update_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "verified",
                "message": "hash ok",
                "device_id": "SAFE-001",
            },
            headers={"X-Device-Token": "m" * 48},
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(request_mock.call_args.kwargs["json"], {
            "update_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "verified",
            "message": "hash ok",
        })

    def test_master_relay_rejects_missing_master_token_before_upstream_request(self):
        response = self.client.get("/api/jarvis/v1/firmware/relay/pending")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "INVALID_DEVICE_CREDENTIAL")

    def test_master_relay_rejects_invalid_status(self):
        response = self.client.post(
            "/api/jarvis/v1/firmware/relay/status",
            json={"update_id": "123e4567-e89b-12d3-a456-426614174000", "status": "skipped"},
            headers={"X-Device-Token": "m" * 48},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "INVALID_UPDATE_STATUS")



if __name__ == "__main__":
    unittest.main()
