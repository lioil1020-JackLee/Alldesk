"""Windows window management helpers."""

import ctypes
import time
from urllib.parse import quote

from app.platform.win_clipboard import (
	paste_via_keyboard_and_enter,
	send_enter_key,
	set_clipboard_text,
)

try:
	from pywinauto import Application as PywinautoApplication
	from pywinauto import Desktop as PywinautoDesktop
	from pywinauto.controls.uiawrapper import UIAWrapper
	from pywinauto.uia_defines import IUIA
	from pywinauto.uia_element_info import UIAElementInfo
except Exception:
	PywinautoApplication = None
	PywinautoDesktop = None
	UIAWrapper = None
	IUIA = None
	UIAElementInfo = None


PASSWORD_KEYIN_DELAY_S = 0.05
CONFIRM_BUTTON_KEYWORDS = (
	"ok",
	"confirm",
	"continue",
	"\u78ba\u5b9a",
	"\u7e7c\u7e8c",
)


def build_unilink_for_id(target_id: str, password: str | None = None) -> str:
	"""Build RustDesk uni-link string for target id/password."""
	try:
		tid = quote(str(target_id))
		if password:
			params = f"password={quote(str(password), safe='')}"
			return f"rustdesk://connect/{tid}?{params}"
		return f"rustdesk://connect/{tid}"
	except Exception:
		return f"rustdesk://connect/{target_id}"


def find_flutter_runner_window(timeout: float = 3.0):
	user32 = ctypes.windll.user32
	class_name = "FLUTTER_RUNNER_WIN32_WINDOW"
	wnd_name = "RustDesk"
	start = time.time()
	while time.time() - start < timeout:
		try:
			hwnd = user32.FindWindowW(class_name, wnd_name)
			if hwnd and hwnd != 0:
				return hwnd
		except Exception:
			pass
		time.sleep(0.12)
	return None


def send_unilink_to_flutter_runner(uni_link: str, timeout_ms: int = 2000) -> bool:
	user32 = ctypes.windll.user32
	SMTO_ABORTIFHUNG = 0x0002
	WM_COPYDATA = 0x004A
	WM_USER = 0x0400

	hwnd = find_flutter_runner_window(timeout=2.0)
	if not hwnd:
		return False

	class COPYDATASTRUCT(ctypes.Structure):
		_fields_ = [
			("dwData", ctypes.c_size_t),
			("cbData", ctypes.c_ulong),
			("lpData", ctypes.c_void_p),
		]

	try:
		data_utf16 = (uni_link + "\x00").encode("utf-16le")
	except Exception:
		data_utf16 = (uni_link + "\x00").encode("utf-16le", errors="replace")

	buf = ctypes.create_string_buffer(data_utf16)
	cds = COPYDATASTRUCT()
	cds.dwData = WM_USER + 2
	cds.cbData = len(data_utf16)
	cds.lpData = ctypes.cast(buf, ctypes.c_void_p)

	try:
		result = user32.SendMessageTimeoutW(
			hwnd,
			WM_COPYDATA,
			0,
			ctypes.byref(cds),
			SMTO_ABORTIFHUNG,
			int(timeout_ms),
			None,
		)
		return bool(result)
	except Exception:
		return False


def find_window_for_id(target_id: str, timeout: float = 6.0, abort_if=None):
	user32 = ctypes.windll.user32
	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	buf = ctypes.create_unicode_buffer(1024)
	class_buf = ctypes.create_unicode_buffer(256)

	def enum_proc(hwnd, lParam):
		try:
			if user32.IsWindowVisible(hwnd):
				user32.GetWindowTextW(hwnd, buf, 1024)
				title = buf.value or ""
				user32.GetClassNameW(hwnd, class_buf, 256)
				class_name = class_buf.value or ""
				if str(target_id) in title and (
					"RustDesk" in title
					or "@" in title
					or class_name == "FLUTTER_RUNNER_WIN32_WINDOW"
				):
					found.append(hwnd)
					return False
		except Exception:
			pass
		return True

	start = time.time()
	found = []
	while time.time() - start < timeout:
		found.clear()
		try:
			user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
		except Exception:
			pass
		if found:
			return found[0]
		try:
			if callable(abort_if) and abort_if():
				return None
		except Exception:
			pass
		time.sleep(0.12)
	return None


def is_rustdesk_id_not_found_dialog_open() -> bool:
	user32 = ctypes.windll.user32
	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	buf = ctypes.create_unicode_buffer(1024)

	error_title_keywords = ["連線錯誤", "连接错误", "connection error", "error", "錯誤", "错误"]
	id_not_found_keywords = ["id不存在", "id 不存在", "id does not exist", "id not found", "invalid id"]

	found = False

	def enum_proc(hwnd, lParam):
		nonlocal found
		try:
			if not user32.IsWindowVisible(hwnd):
				return True
			user32.GetWindowTextW(hwnd, buf, 1024)
			title = (buf.value or "").strip()
			if not title:
				return True
			title_low = title.lower()
			if not any(k in title_low for k in error_title_keywords):
				return True

			texts = [title]

			def child_proc(ch, _):
				try:
					user32.GetWindowTextW(ch, buf, 1024)
					t = (buf.value or "").strip()
					if t:
						texts.append(t)
				except Exception:
					pass
				return True

			try:
				user32.EnumChildWindows(hwnd, WNDENUMPROC(child_proc), 0)
			except Exception:
				pass

			merged = " ".join(texts).lower()
			merged_no_space = merged.replace(" ", "")
			for kw in id_not_found_keywords:
				k = kw.lower()
				if k in merged or k.replace(" ", "") in merged_no_space:
					found = True
					return False
		except Exception:
			pass
		return True

	try:
		user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
	except Exception:
		return False
	return found


def is_rustdesk_connection_error_dialog_open() -> bool:
	user32 = ctypes.windll.user32
	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	buf = ctypes.create_unicode_buffer(1024)

	title_keywords = ["連線錯誤", "连接错误", "connection error"]
	ok_keywords = ["確定", "确定", "ok"]

	found = False

	def enum_proc(hwnd, lParam):
		nonlocal found
		try:
			if not user32.IsWindowVisible(hwnd):
				return True
			user32.GetWindowTextW(hwnd, buf, 1024)
			title = (buf.value or "").strip()
			if not title:
				return True
			title_low = title.lower()
			if not any(k in title_low for k in title_keywords):
				return True

			texts = [title]

			def child_proc(ch, _):
				try:
					user32.GetWindowTextW(ch, buf, 1024)
					t = (buf.value or "").strip()
					if t:
						texts.append(t)
				except Exception:
					pass
				return True

			try:
				user32.EnumChildWindows(hwnd, WNDENUMPROC(child_proc), 0)
			except Exception:
				pass

			merged = " ".join(texts).lower()
			if any(k in merged for k in ok_keywords):
				found = True
				return False
		except Exception:
			pass
		return True

	try:
		user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
	except Exception:
		return False
	return found


def find_password_dialog(timeout: float = 6.0):
	user32 = ctypes.windll.user32
	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	buf = ctypes.create_unicode_buffer(1024)
	password_keywords = [
		"密碼", "需要密碼", "驗證 rustdesk 密碼", "輸入您的密碼",
		"密码", "需要密码", "验证 rustdesk 密码", "输入您的密码",
		"rustdesk 密碼", "rustdesk 密码", "rustdesk password",
		"password", "enter password", "passwort", "passwort erforderlich",
		"mot de passe", "entrez le mot de passe", "contraseña",
		"introduzca la contraseña", "パスワード", "パスワード入力",
		"비밀번호", "비밀번호 입력",
	]

	def enum_proc(hwnd, lParam):
		try:
			if not user32.IsWindowVisible(hwnd):
				return True
			user32.GetWindowTextW(hwnd, buf, 1024)
			title = (buf.value or "").strip()
			texts = [title] if title else []

			def child_proc(ch, _):
				try:
					user32.GetWindowTextW(ch, buf, 1024)
					t = (buf.value or "").strip()
					if t:
						texts.append(t)
				except Exception:
					pass
				return True

			try:
				user32.EnumChildWindows(hwnd, WNDENUMPROC(child_proc), 0)
			except Exception:
				pass

			merged = " ".join(texts).lower()
			if any(keyword in merged for keyword in password_keywords):
				found.append(hwnd)
				return False
		except Exception:
			pass
		return True

	start = time.time()
	found = []
	while time.time() - start < timeout:
		found.clear()
		try:
			user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
		except Exception:
			pass
		if found:
			return found[0]
		try:
			if PywinautoDesktop is not None:
				for win in PywinautoDesktop(backend="uia").windows():
					try:
						title = (win.window_text() or "").lower()
						if not (
							"rustdesk" in title
							or "@" in title
							or "密碼" in title
							or "密码" in title
							or "password" in title
						):
							continue
						texts = [title]
						try:
							for child in win.descendants()[:120]:
								name = (child.element_info.name or "").strip()
								if name:
									texts.append(name.lower())
						except Exception:
							pass
						merged = " ".join(texts)
						if any(keyword in merged for keyword in password_keywords):
							try:
								return int(win.handle)
							except Exception:
								return win.handle
					except Exception:
						continue
		except Exception:
			pass
		time.sleep(0.12)
	return None


def _input_password_into_edit(edit, password: str, hwnd=None) -> bool:
	try:
		if hwnd:
			try:
				force_foreground(hwnd)
			except Exception:
				pass
		try:
			edit.set_focus()
		except Exception:
			pass
		time.sleep(PASSWORD_KEYIN_DELAY_S)
		try:
			edit.set_edit_text(str(password))
			edit.type_keys("{ENTER}")
			send_enter_key(times=2, delay=0.05)
			_click_confirm_button(hwnd)
			return True
		except Exception:
			pass
		try:
			edit.type_keys("^a{BACKSPACE}")
		except Exception:
			pass
		if set_clipboard_text(str(password)):
			time.sleep(0.08)
			if paste_via_keyboard_and_enter():
				return True
		def _escape_for_type_keys(s: str) -> str:
			special = set("^%+~{}()[]")
			out = []
			for ch in s:
				out.append("{" + ch + "}" if ch in special else ch)
			return "".join(out)
		edit.type_keys(
			_escape_for_type_keys(str(password)),
			with_spaces=True,
			set_foreground=True,
		)
		edit.type_keys("{ENTER}")
		send_enter_key(times=2, delay=0.05)
		_click_confirm_button(hwnd)
		return True
	except Exception:
		return False


def _click_confirm_button(hwnd=None) -> bool:
	try:
		if PywinautoApplication is not None and hwnd:
			app = PywinautoApplication(backend="uia").connect(handle=hwnd)
			dlg = app.window(handle=hwnd)
			for button in dlg.descendants(control_type="Button"):
				try:
					name = (button.element_info.name or button.window_text() or "").strip()
					if any(k in name.lower() for k in CONFIRM_BUTTON_KEYWORDS):
						button.click_input()
						return True
				except Exception:
					continue
	except Exception:
		pass
	try:
		if PywinautoDesktop is not None:
			for win in PywinautoDesktop(backend="uia").windows():
				try:
					title = (win.window_text() or "").lower()
					if "rustdesk" not in title and "@" not in title:
						continue
					for button in win.descendants(control_type="Button"):
						try:
							name = (button.element_info.name or button.window_text() or "").strip()
							if any(k in name.lower() for k in CONFIRM_BUTTON_KEYWORDS):
								button.click_input()
								return True
						except Exception:
							continue
				except Exception:
					continue
	except Exception:
		pass
	return False


def try_focused_uia_password(password: str) -> tuple[bool, bool]:
	"""Fill the currently focused password edit without scanning the UIA tree."""
	if IUIA is None or UIAElementInfo is None or UIAWrapper is None:
		return False, False
	try:
		element = IUIA().iuia.GetFocusedElement()
		if not element:
			return False, False
		info = UIAElementInfo(element)
		control_type = (info.control_type or "").strip().lower()
		name = (info.name or "").strip().lower()
		is_password = bool(getattr(info, "is_password", False))
		password_names = (
			"password",
			"passwort",
			"mot de passe",
			"contraseña",
			"密碼",
			"密码",
		)
		if control_type != "edit" and not is_password:
			return False, False
		if not is_password and name and not any(word in name for word in password_names):
			return False, False
		wrapper = UIAWrapper(info)
		return _input_password_into_edit(wrapper, str(password)), True
	except Exception:
		return False, False


def wait_and_input_password(password: str, max_wait_time: float = 5.0) -> tuple[bool, bool]:
	start_time = time.time()
	check_interval = 0.02
	last_attempt_time = 0
	attempt_cooldown = 0.08
	saw_password_dialog = False

	while time.time() - start_time < max_wait_time:
		current_time = time.time()
		pwd_hwnd = find_password_dialog(timeout=0.05)
		if pwd_hwnd:
			saw_password_dialog = True
			if current_time - last_attempt_time < attempt_cooldown:
				time.sleep(check_interval)
				continue

			try:
				force_foreground(pwd_hwnd)

				if try_uia_set_password(pwd_hwnd, password):
					return True, True

				if set_clipboard_text(password):
					time.sleep(0.05)
					if paste_via_keyboard_and_enter():
						return True, True
			except Exception:
				pass

			last_attempt_time = current_time

		elif saw_password_dialog and current_time - last_attempt_time >= attempt_cooldown:
			try:
				if try_uia_set_password(0, password):
					return True, True
			except Exception:
				pass
			last_attempt_time = current_time

		time.sleep(check_interval)

	return False, saw_password_dialog


def close_window(hwnd: int) -> bool:
	try:
		user32 = ctypes.windll.user32
		WM_CLOSE = 0x0010
		return bool(user32.PostMessageW(int(hwnd), WM_CLOSE, 0, 0))
	except Exception:
		return False


def send_unilink_via_copydata(hwnd_target, uni_link: str) -> bool:
	user32 = ctypes.windll.user32
	WM_COPYDATA = 0x004A
	WM_USER = 0x0400

	class COPYDATASTRUCT(ctypes.Structure):
		_fields_ = [
			("dwData", ctypes.c_size_t),
			("cbData", ctypes.c_ulong),
			("lpData", ctypes.c_void_p),
		]

	def _try_send(data_bytes):
		try:
			buf = ctypes.create_string_buffer(data_bytes)
			cds = COPYDATASTRUCT()
			cds.dwData = WM_USER + 2
			cds.cbData = len(data_bytes)
			cds.lpData = ctypes.cast(buf, ctypes.c_void_p)
			res = user32.SendMessageW(hwnd_target, WM_COPYDATA, 0, ctypes.byref(cds))
			return int(res) != 0
		except Exception:
			return False

	try:
		data_utf8 = uni_link.encode("utf-8")
	except Exception:
		data_utf8 = uni_link.encode("utf-8", errors="replace")
	if _try_send(data_utf8):
		return True

	try:
		data_utf16 = (uni_link + "\x00").encode("utf-16le")
	except Exception:
		data_utf16 = (uni_link + "\x00").encode("utf-16le", errors="replace")
	if _try_send(data_utf16):
		return True
	return False


def try_uia_set_password(hwnd, password: str) -> bool:
	try:
		if hwnd and PywinautoApplication is not None:
			app = PywinautoApplication(backend="uia").connect(handle=hwnd)
			dlg = app.window(handle=hwnd)
			try:
				pw_edit = dlg.child_window(control_type="Edit")
				if _input_password_into_edit(pw_edit, password, hwnd):
					return True
			except Exception:
				pass
			try:
				edits = dlg.descendants(control_type="Edit")
				for edit in edits:
					if _input_password_into_edit(edit, password, hwnd):
						return True
			except Exception:
				pass
		try:
			if PywinautoDesktop is not None:
				for win in PywinautoDesktop(backend="uia").windows():
					try:
						title = (win.window_text() or "").lower()
						if "rustdesk" not in title and "@" not in title:
							continue
						for edit in win.descendants(control_type="Edit"):
							if _input_password_into_edit(edit, password, win.handle):
								return True
					except Exception:
						continue
		except Exception:
			pass
		try:
			if set_clipboard_text(password):
				try:
					force_foreground(hwnd)
				except Exception:
					pass
				time.sleep(0.12)
				if paste_via_keyboard_and_enter():
					return True
		except Exception:
			return False
	except Exception:
		return False


def force_foreground(hwnd: int) -> bool:
	try:
		user32 = ctypes.windll.user32
		SW_RESTORE = 9
		try:
			try:
				if user32.IsIconic(hwnd):
					user32.ShowWindow(hwnd, SW_RESTORE)
			except Exception:
				pass
		except Exception:
			pass
		try:
			user32.SetForegroundWindow(hwnd)
			user32.BringWindowToTop(hwnd)
			return True
		except Exception:
			pass

		try:
			GetWindowThreadProcessId = user32.GetWindowThreadProcessId
			GetWindowThreadProcessId.restype = ctypes.c_ulong
			pid = ctypes.c_ulong()
			fg = user32.GetForegroundWindow()
			cur_tid = GetWindowThreadProcessId(fg, ctypes.byref(pid))
			tgt_pid = ctypes.c_ulong()
			tgt_tid = GetWindowThreadProcessId(hwnd, ctypes.byref(tgt_pid))

			AttachThreadInput = user32.AttachThreadInput
			AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool]
			AttachThreadInput.restype = ctypes.c_bool

			if AttachThreadInput(cur_tid, tgt_tid, True):
				try:
					user32.SetForegroundWindow(hwnd)
					user32.BringWindowToTop(hwnd)
				finally:
					AttachThreadInput(cur_tid, tgt_tid, False)
				return True
		except Exception:
			pass
	except Exception:
		pass
	return False

