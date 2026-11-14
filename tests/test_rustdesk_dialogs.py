import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.platform import rustdesk_dialogs as dialogs


class Control:
    def __init__(self, name, kind="Text", *, password=False, enabled=True):
        self.element_info = SimpleNamespace(
            name=name, control_type=kind,
            element=SimpleNamespace(CurrentIsPassword=password),
        )
        self.iface_invoke = SimpleNamespace(Invoke=Mock())
        self.iface_value = SimpleNamespace(SetValue=Mock())
        self.click_input = Mock()
        self.set_focus = Mock()
        self.enabled = enabled

    def is_visible(self):
        return True

    def is_enabled(self):
        return self.enabled


class RustDeskDialogsTests(unittest.TestCase):
    def setUp(self):
        self.foreground_original = dialogs.foreground_session_window
        self.foreground = patch.object(dialogs, "foreground_session_window", return_value=123).start()
        self.desktop = patch.object(dialogs, "PywinautoDesktop").start()
        self.window = self.desktop.return_value.window.return_value.wrapper_object.return_value
        self.addCleanup(patch.stopall)

    def show(self, *controls):
        self.window.descendants.return_value = list(controls)

    def handle(self, **kwargs):
        return dialogs.try_connection_dialog("47398667", "test-密碼^+{}", **kwargs)

    def test_warning_then_password_only_invokes_intended_buttons(self):
        continue_button = Control("繼續", "Button")
        disconnect = Control("中斷連線", "Button")
        self.show(Control("非安全連線"), continue_button, disconnect)
        self.assertEqual(self.handle(), "continued")
        continue_button.iface_invoke.Invoke.assert_called_once_with()
        disconnect.iface_invoke.Invoke.assert_not_called()

        search = Control("搜尋", "Edit")
        password = Control("密碼", "Edit", password=True)
        confirm = Control("確定", "Button")
        cancel = Control("取消", "Button")
        self.show(Control("需要密碼"), search, password, cancel, confirm)
        self.assertEqual(self.handle(allow_continue=False), "submitted")
        password.iface_value.SetValue.assert_called_once_with("test-密碼^+{}")
        search.iface_value.SetValue.assert_not_called()
        confirm.iface_invoke.Invoke.assert_called_once_with()
        cancel.iface_invoke.Invoke.assert_not_called()

    def test_localized_warning_and_invoke_pattern_fallback(self):
        for title, label in [("不安全连接", "继续"), ("Insecure Connection", "Continue")]:
            with self.subTest(title=title):
                button = Control(label, "Button")
                button.iface_invoke.Invoke.side_effect = RuntimeError("No InvokePattern")
                self.show(Control(title), button)
                self.assertEqual(self.handle(), "continued")
                button.click_input.assert_called_once_with()

    def test_other_foreground_app_or_session_is_never_scanned(self):
        self.foreground.return_value = None
        self.assertEqual(self.handle(), "waiting")
        self.desktop.assert_not_called()

    def test_unrelated_continue_button_is_untouched(self):
        button = Control("Continue", "Button")
        self.show(Control("Transfer file"), button)
        self.assertEqual(self.handle(), "waiting")
        button.iface_invoke.Invoke.assert_not_called()

    def test_warning_is_not_clicked_twice_during_transition(self):
        button = Control("繼續", "Button")
        self.show(Control("非安全連線"), button)
        self.assertEqual(self.handle(allow_continue=False), "waiting")
        button.iface_invoke.Invoke.assert_not_called()

    def test_disabled_continue_waits_until_enabled(self):
        button = Control("繼續", "Button", enabled=False)
        self.show(Control("非安全連線"), button)
        self.assertEqual(self.handle(), "waiting")
        button.iface_invoke.Invoke.assert_not_called()
        button.enabled = True
        self.assertEqual(self.handle(), "continued")

    def test_keyboard_fallback_does_not_type_after_focus_changes(self):
        edit = Control("密碼", "Edit", password=True)
        edit.iface_value.SetValue.side_effect = RuntimeError("No ValuePattern")
        self.show(Control("需要密碼"), edit, Control("確定", "Button"))
        self.foreground.side_effect = [123, 123, None]
        with patch("pywinauto.keyboard.send_keys") as send_keys:
            self.assertEqual(self.handle(), "password")
            send_keys.assert_not_called()

    def test_keyboard_fallback_escapes_special_characters_and_submits_once(self):
        edit = Control("密碼", "Edit", password=True)
        edit.iface_value.SetValue.side_effect = RuntimeError("No ValuePattern")
        confirm = Control("確定", "Button")
        self.show(Control("需要密碼"), edit, confirm)
        with patch.object(dialogs, "IUIA") as automation, patch("pywinauto.keyboard.send_keys") as send_keys:
            automation.return_value.iuia.CompareElements.return_value = True
            self.assertEqual(self.handle(), "submitted")
            self.assertEqual(send_keys.call_args_list[1].args[0], "test-密碼{^}{+}{{}{}}")
        confirm.iface_invoke.Invoke.assert_called_once_with()

    def test_error_does_not_fill_password(self):
        edit = Control("密碼", "Edit", password=True)
        self.show(Control("密碼錯誤"), edit, Control("確定", "Button"))
        self.assertEqual(self.handle(), "error")
        edit.iface_value.SetValue.assert_not_called()

    def test_exact_session_id_matching(self):
        self.assertTrue(dialogs.session_title_matches("47398667@desktop", "47398667"))
        self.assertTrue(dialogs.session_title_matches("RustDesk - 47398667", "47398667"))
        for title in ("147398667@desktop", "473986670@desktop", "other@desktop", ""):
            with self.subTest(title=title):
                self.assertFalse(dialogs.session_title_matches(title, "47398667"))

    def test_real_rustdesk_153_multiwindow_class_is_accepted(self):
        # Regression: the actual 1.5.3 connection uses RustdeskMultiWindow,
        # while the main Flutter runner uses a different native window class.
        user32 = Mock()
        user32.GetForegroundWindow.return_value = 123
        user32.GetWindowTextW.side_effect = lambda hwnd, buf, size: setattr(buf, "value", "47398667@desktop - RustDesk")
        with patch.object(ctypes.windll, "user32", user32):
            for class_name, expected in [
                ("RustdeskMultiWindow", 123),
                ("FLUTTER_RUNNER_WIN32_WINDOW", 123),
                ("Chrome_WidgetWin_1", None),
            ]:
                user32.GetClassNameW.side_effect = lambda hwnd, buf, size, name=class_name: setattr(buf, "value", name)
                with self.subTest(class_name=class_name):
                    # setUp patches the public function; use the original here.
                    self.assertEqual(self.foreground_original("47398667"), expected)


if __name__ == "__main__":
    unittest.main()
