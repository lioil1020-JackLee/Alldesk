import threading
import time
import unittest

from app.ui.tabs.rustdesk_tab import RustDesk


class RustDeskPasswordWatcherTests(unittest.TestCase):
    def test_focused_password_field_is_handled_immediately(self):
        rustdesk = RustDesk.__new__(RustDesk)
        rustdesk._password_watcher_lock = threading.Lock()
        rustdesk._password_watcher_stop = None
        rustdesk._foreground_title_for_client = lambda client_id: f"{client_id}@server"
        rustdesk._is_rustdesk_id_not_found_dialog_open = lambda: False
        rustdesk._is_rustdesk_connection_error_dialog_open = lambda: False
        rustdesk._wait_and_input_password = lambda password, max_wait_time: (False, False)

        calls = []

        def focused_input(password):
            calls.append((password, time.monotonic()))
            return True, True

        rustdesk._try_focused_uia_password = focused_input
        started = time.monotonic()
        result = rustdesk._start_password_input_watcher("47398667", "secret", 1.0)

        deadline = time.monotonic() + 0.5
        while not result["ok"] and time.monotonic() < deadline:
            time.sleep(0.005)

        self.assertTrue(result["ok"])
        self.assertTrue(result["saw"])
        self.assertEqual(calls[0][0], "secret")
        self.assertLess(calls[0][1] - started, 0.15)


if __name__ == "__main__":
    unittest.main()
