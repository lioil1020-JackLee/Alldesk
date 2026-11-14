import threading
import time
import unittest

from app.ui.tabs.rustdesk_tab import RustDesk


class RustDeskPasswordWatcherTests(unittest.TestCase):
    def watcher(self, callback):
        rustdesk = RustDesk.__new__(RustDesk)
        rustdesk._password_watcher_lock = threading.Lock()
        rustdesk._password_watcher_stop = None
        rustdesk._try_connection_dialog = callback
        return rustdesk

    def wait_done(self, result):
        deadline = time.monotonic() + 1.5
        while not result["done"] and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(result["done"])

    def test_continue_then_password_without_initial_two_second_delay(self):
        calls = []

        def handle(client_id, password, *, allow_continue):
            calls.append((client_id, password, allow_continue, time.monotonic()))
            return "continued" if len(calls) == 1 else "submitted"

        rustdesk = self.watcher(handle)
        result = rustdesk._start_password_input_watcher("47398667", "secret", 1.0)
        self.wait_done(result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["saw"])
        self.assertTrue(result["continued"])
        self.assertEqual([call[2] for call in calls], [True, False])
        self.assertEqual(calls[1][:2], ("47398667", "secret"))
        self.assertLess(calls[1][3] - calls[0][3], 0.25)

    def test_password_is_handled_on_first_tick_after_manual_continue(self):
        calls = []

        def handle(*args, **kwargs):
            calls.append(time.monotonic())
            return "submitted"

        rustdesk = self.watcher(handle)
        started = time.monotonic()
        result = rustdesk._start_password_input_watcher("47398667", "secret", 1.0)
        self.wait_done(result)
        self.assertTrue(result["ok"])
        self.assertFalse(result["continued"])
        self.assertEqual(len(calls), 1)
        self.assertLess(calls[0] - started, 0.5)

    def test_error_stops_watcher_and_returns_without_waiting_25_seconds(self):
        rustdesk = self.watcher(lambda *args, **kwargs: "error")
        result = rustdesk._start_password_input_watcher("47398667", "secret", 1.0)
        self.wait_done(result)
        started = time.monotonic()
        self.assertEqual(rustdesk._wait_for_password_watcher(result), (False, False))
        self.assertLess(time.monotonic() - started, 0.1)


if __name__ == "__main__":
    unittest.main()
