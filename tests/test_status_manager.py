import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.status_manager import StatusManager, _PeerState


class _Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


class StatusManagerTests(unittest.TestCase):
    def test_unknown_to_concrete_admin_status_is_applied_immediately(self):
        manager = StatusManager(
            "example.local",
            5014,
            timeout_s=5,
            interval_s=1,
            status_change_confirm_polls=4,
            admin_online_window_s=45,
        )
        manager.set_peer_ids(["123"])
        now = time.time()
        manager._states["123"] = _PeerState(online=None, updated_at=now, error_at=now)

        def fake_post(url, **kwargs):
            if url.endswith("/api/admin/login"):
                return _Response({"data": {"token": "admin-token"}})
            return _Response({}, status_code=404)

        def fake_get(url, **kwargs):
            self.assertTrue(url.endswith("/api/admin/peer/list"))
            return _Response(
                {
                    "code": 0,
                    "data": {
                        "total": 1,
                        "list": [{"id": "123", "last_online_time": int(time.time())}],
                    },
                }
            )

        fake_requests = SimpleNamespace(get=fake_get, post=fake_post)
        manager.api_username = "admin"
        manager.api_password = "secret"
        with patch("app.services.status_manager.requests", fake_requests):
            manager._poll_once()

        self.assertIs(manager.get_cached_status("123"), True)
        self.assertNotIn("123", manager._pending)

    def test_poll_uses_admin_list_without_address_book_or_peers(self):
        manager = StatusManager(
            "example.local",
            5014,
            timeout_s=5,
            first_poll_timeout_s=2.0,
            interval_s=1,
            admin_online_window_s=45,
        )
        manager.set_peer_ids(["123", "456"])
        seen_urls = []

        def fake_post(url, **kwargs):
            self.assertEqual(kwargs["timeout"], 2.0)
            if url.endswith("/api/admin/login"):
                return _Response({"data": {"token": "admin-token"}})
            return _Response({}, status_code=404)

        def fake_get(url, **kwargs):
            self.assertEqual(kwargs["timeout"], 2.0)
            seen_urls.append(url)
            self.assertFalse(url.endswith("/api/ab"))
            self.assertFalse(url.endswith("/api/peers"))
            self.assertEqual(kwargs["params"]["page_size"], 100)
            self.assertEqual(kwargs["params"]["page"], 1)
            return _Response(
                {
                    "code": 0,
                    "data": {
                        "total": 2,
                        "list": [
                            {"id": "123", "last_online_time": int(time.time())},
                            {"id": "456", "last_online_time": 0},
                        ],
                    },
                }
            )

        fake_requests = SimpleNamespace(get=fake_get, post=fake_post)
        manager.api_username = "admin"
        manager.api_password = "secret"
        with patch("app.services.status_manager.requests", fake_requests):
            manager._poll_once()

        self.assertEqual(len(seen_urls), 1)
        self.assertIs(manager.get_cached_status("123"), True)
        self.assertIs(manager.get_cached_status("456"), False)

    def test_large_admin_list_paginates_until_all_rows_are_read(self):
        manager = StatusManager("example.local", 5014, first_poll_timeout_s=3.0)
        manager.set_peer_ids(["123", "456"] + [f"x{i}" for i in range(79)])
        pages = []

        def fake_post(url, **kwargs):
            if url.endswith("/api/admin/login"):
                return _Response({"data": {"token": "admin-token"}})
            return _Response({}, status_code=404)

        def fake_get(url, **kwargs):
            page = kwargs["params"]["page"]
            pages.append(page)
            self.assertEqual(kwargs["params"]["page_size"], 100)
            if page == 1:
                return _Response(
                    {
                        "code": 0,
                        "data": {
                            "total": 250,
                            "list": [{"id": "123", "last_online_time": 0}],
                        },
                    }
                )
            if page == 2:
                return _Response(
                    {
                        "code": 0,
                        "data": {
                            "total": 250,
                            "list": [{"id": "456", "last_online_time": int(time.time())}],
                        },
                    }
                )
            return _Response(
                {
                    "code": 0,
                    "data": {
                        "total": 250,
                        "list": [],
                    },
                }
            )

        fake_requests = SimpleNamespace(get=fake_get, post=fake_post)
        manager.api_username = "admin"
        manager.api_password = "secret"
        with patch("app.services.status_manager.requests", fake_requests):
            manager._poll_once()

        self.assertEqual(pages, [1, 2, 3])
        self.assertIs(manager.get_cached_status("123"), False)
        self.assertIs(manager.get_cached_status("456"), True)

    def test_status_field_coercion_accepts_common_variants(self):
        manager = StatusManager("example.local", 5014)
        self.assertIs(manager._coerce_online({"status": "online"}), True)
        self.assertIs(manager._coerce_online({"state": "offline"}), False)
        self.assertIs(manager._coerce_online({"isOnline": True}), True)

    def test_duplicate_admin_rows_keep_online_status(self):
        manager = StatusManager(
            "example.local",
            5014,
            first_poll_timeout_s=3.0,
            admin_online_window_s=45,
        )
        manager.set_peer_ids(["123"])

        def fake_post(url, **kwargs):
            if url.endswith("/api/admin/login"):
                return _Response({"data": {"token": "admin-token"}})
            return _Response({}, status_code=404)

        def fake_get(url, **kwargs):
            return _Response(
                {
                    "code": 0,
                    "data": {
                        "total": 2,
                        "list": [
                            {"id": "123", "last_online_time": int(time.time())},
                            {"id": "123", "last_online_time": 0},
                        ],
                    },
                }
            )

        fake_requests = SimpleNamespace(get=fake_get, post=fake_post)
        manager.api_username = "admin"
        manager.api_password = "secret"
        with patch("app.services.status_manager.requests", fake_requests):
            manager._poll_once()

        self.assertIs(manager.get_cached_status("123"), True)

    def test_startup_timeout_remains_long_until_a_concrete_status_exists(self):
        manager = StatusManager(
            "example.local",
            5014,
            timeout_s=1.0,
            first_poll_timeout_s=3.0,
        )
        manager._poll_count = 2
        self.assertEqual(manager._request_timeout(), 3.0)

        manager._states["123"] = _PeerState(
            online=True,
            updated_at=time.time(),
            error_at=None,
        )
        self.assertEqual(manager._request_timeout(), 1.0)

    def test_failed_admin_poll_keeps_previous_concrete_status(self):
        manager = StatusManager("example.local", 5014, cache_grace_s=60)
        manager.set_peer_ids(["123"])
        manager._states["123"] = _PeerState(
            online=True,
            updated_at=time.time(),
            error_at=None,
        )
        manager._admin_token = "admin-token"
        manager._admin_token_expires_at = time.time() + 60

        fake_requests = SimpleNamespace(
            get=lambda *args, **kwargs: _Response({}, status_code=503),
            post=lambda *args, **kwargs: _Response({}, status_code=503),
        )
        with patch("app.services.status_manager.requests", fake_requests):
            manager._poll_once()

        self.assertIs(manager.get_cached_status("123"), True)


if __name__ == "__main__":
    unittest.main()
