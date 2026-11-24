import unittest
from unittest.mock import patch

import main


class WebAlertTests(unittest.TestCase):
    def setUp(self):
        main.alert_events.clear()
        main._alert_state_by_device.clear()
        self.device = {
            "device_id": "SAFE-001",
            "site_name": "แผงหลัก",
            "customer_id": "CUST-0891",
            "province": "ขอนแก่น",
            "alert_level": "warning",
            "fault_list": ["⚠️ อุณหภูมิสูง: 61°C"],
            "last_alert_sent": None,
        }

    @patch.object(main, "_persist_web_alert_event", return_value=True)
    @patch.object(main, "send_email_alert")
    def test_creates_web_event_without_email(self, email_sender, persist):
        main.trigger_alert(self.device)
        self.assertEqual(len(main.alert_events), 1)
        self.assertEqual(main.alert_events[0]["device_id"], "SAFE-001")
        self.assertEqual(main.alert_events[0]["level"], "warning")
        persist.assert_called_once()
        email_sender.assert_not_called()

    @patch.object(main, "_persist_web_alert_event", return_value=True)
    def test_same_fault_is_not_repeated_immediately(self, persist):
        main.trigger_alert(self.device)
        main.trigger_alert(self.device)
        self.assertEqual(len(main.alert_events), 1)
        persist.assert_called_once()

    @patch.object(main, "_persist_web_alert_event", return_value=True)
    def test_new_fault_signature_creates_new_event(self, persist):
        main.trigger_alert(self.device)
        changed = dict(self.device)
        changed["fault_list"] = ["🔴 แรงดันผิดปกติ"]
        changed["alert_level"] = "critical"
        main.trigger_alert(changed)
        self.assertEqual(len(main.alert_events), 2)
        self.assertEqual(main.alert_events[0]["level"], "critical")

    @patch.object(main, "_safe_elec_project_id", return_value=None)
    def test_alert_history_api_is_session_scoped(self, _project):
        main.alert_events.append({
            "event_id": "test-event",
            "device_id": "SAFE-001",
            "customer_id": "CUST-0891",
            "level": "warning",
            "status_text": "มีสิ่งต้องเฝ้าระวัง",
            "faults": ["test"],
            "occurred_at": "2026-11-24T00:00:00+07:00",
        })
        client = main.app.test_client()
        with client.session_transaction() as session:
            session["username"] = "cust0891"
            session["cust_id"] = "CUST-0891"
        response = client.get("/api/alerts")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["events"][0]["event_id"], "test-event")


if __name__ == "__main__":
    unittest.main()
