import unittest

from app.services import status_service


class StatusServiceTests(unittest.TestCase):
    def test_get_rustdesk_peer_ids_skips_disabled_status_clients(self):
        clients = [
            {"tag": "A", "id": "111", "check_status": True},
            {"tag": "B", "id": "222", "check_status": False},
            {"tag": "C", "id": "333"},
        ]

        out = status_service.get_rustdesk_peer_ids(
            lambda section: clients,
            lambda client: {
                "id": str(client.get("id", "")),
                "check_status": client.get("check_status", True),
            },
        )

        self.assertEqual(out, ["111", "333"])

    def test_compute_rustdesk_status_ignores_disabled_client(self):
        class _Manager:
            def get_cached_status(self, peer_id):
                raise AssertionError("disabled clients should not query cache")

        status = status_service.compute_client_status(
            "rustdesk",
            {"id": "222", "check_status": False},
            lambda client: client,
            _Manager(),
            lambda host: True,
            lambda host, port: True,
        )

        self.assertEqual(status, "error")


if __name__ == "__main__":
    unittest.main()
