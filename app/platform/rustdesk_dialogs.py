"""Handle connection prompts only in the requested RustDesk session."""

import ctypes
import re

from app.platform.win_window import IUIA, PywinautoDesktop


INSECURE_TITLES = ("非安全連線", "不安全連線", "非安全连接", "不安全连接", "insecure connection")
PASSWORD_TITLES = ("需要密碼", "需要密码", "password required")
ERROR_TITLES = ("連線錯誤", "连接错误", "connection error", "密碼錯誤", "密码错误", "wrong password")
CONTINUE_NAMES = ("繼續", "继续", "continue")
CONFIRM_NAMES = ("確定", "确定", "ok", "confirm")
SESSION_WINDOW_CLASSES = ("FLUTTER_RUNNER_WIN32_WINDOW", "RustdeskMultiWindow")


def session_title_matches(title: str, client_id: str) -> bool:
    target = str(client_id).strip()
    return bool(target and re.search(r"(?<![\w])" + re.escape(target) + r"(?![\w])", title))


def foreground_session_window(client_id: str):
    """Require both the Flutter window class and an exact target ID."""
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    title = ctypes.create_unicode_buffer(1024)
    class_name = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, len(title))
    user32.GetClassNameW(ctypes.c_void_p(hwnd), class_name, len(class_name))
    if class_name.value not in SESSION_WINDOW_CLASSES:
        return None
    return hwnd if session_title_matches(title.value, client_id) else None


def _name(control) -> str:
    return (control.element_info.name or "").strip().casefold()


def _button(controls, names):
    for control in controls:
        if control.element_info.control_type == "Button" and _name(control) in names:
            if control.is_enabled():
                return control
    return None


def _is_password(edit) -> bool:
    try:
        return bool(edit.element_info.element.CurrentIsPassword)
    except Exception:
        return bool(getattr(edit.element_info, "is_password", False))


def _invoke(button):
    # InvokePattern avoids mouse movement, DPI assumptions and default-button Enter.
    try:
        button.iface_invoke.Invoke()
    except Exception:
        # Flutter versions without InvokePattern can still expose clickable bounds.
        button.click_input()


def _fill_password(edit, password: str, hwnd, client_id: str) -> bool:
    try:
        # Use the pattern directly: set_edit_text also logs the secret value.
        edit.iface_value.SetValue(str(password))
        return True
    except Exception:
        pass

    # Some Flutter versions expose password fields without ValuePattern.
    # Send Unicode keys only after verifying the exact field and session focus.
    try:
        from pywinauto.keyboard import send_keys

        edit.set_focus()
        if foreground_session_window(client_id) != hwnd or IUIA is None:
            return False
        automation = IUIA().iuia
        if not automation.CompareElements(edit.element_info.element, automation.GetFocusedElement()):
            return False
        escaped = "".join("{" + char + "}" if char in "^%+~{}()[]" else char for char in str(password))
        send_keys("^a{BACKSPACE}", pause=0.001)
        send_keys(escaped, with_spaces=True, pause=0.001)
        return True
    except Exception:
        return False


def try_connection_dialog(client_id: str, password: str, *, allow_continue: bool = True) -> str:
    """Return waiting, continued, password, submitted or error; never scan other apps."""
    try:
        hwnd = foreground_session_window(client_id)
        if not hwnd or PywinautoDesktop is None:
            return "waiting"
        window = PywinautoDesktop(backend="uia").window(handle=hwnd).wrapper_object()
        controls = [control for control in window.descendants() if control.is_visible()]
        names = [_name(control) for control in controls]
        if any(title in name for title in INSECURE_TITLES for name in names):
            button = _button(controls, CONTINUE_NAMES)
            if allow_continue and button is not None and foreground_session_window(client_id) == hwnd:
                _invoke(button)
                return "continued"
            return "waiting"
        if any(title in name for title in ERROR_TITLES for name in names):
            return "error"

        password_prompt = any(title in name for title in PASSWORD_TITLES for name in names)
        edits = [control for control in controls if control.element_info.control_type == "Edit"]
        edits.sort(key=lambda edit: not _is_password(edit))
        for edit in edits:
            if edit.element_info.control_type != "Edit":
                continue
            named_password = any(word in _name(edit) for word in ("password", "密碼", "密码"))
            if not (_is_password(edit) or (password_prompt and named_password)):
                continue
            button = _button(controls, CONFIRM_NAMES)
            if button is None or foreground_session_window(client_id) != hwnd:
                return "password"
            if not _fill_password(edit, password, hwnd, client_id):
                return "password"
            if foreground_session_window(client_id) != hwnd:
                return "password"
            _invoke(button)
            return "submitted"
    except Exception:
        # A prompt can disappear between UIA calls. Retry on the next watcher tick.
        pass
    return "waiting"
