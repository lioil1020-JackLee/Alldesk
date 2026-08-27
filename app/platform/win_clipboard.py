"""Windows clipboard and paste helpers."""

import ctypes
import time


def set_clipboard_text(text: str) -> bool:
	"""Put Unicode text into system clipboard using WinAPI."""
	try:
		CF_UNICODETEXT = 13
		GMEM_MOVEABLE = 0x0002
		kernel32 = ctypes.windll.kernel32
		user32 = ctypes.windll.user32

		data = (text + "\x00").encode("utf-16le")
		hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
		if not hglobal:
			return False
		ptr = kernel32.GlobalLock(hglobal)
		if not ptr:
			kernel32.GlobalFree(hglobal)
			return False
		ctypes.memmove(ptr, data, len(data))
		kernel32.GlobalUnlock(hglobal)

		if not user32.OpenClipboard(None):
			kernel32.GlobalFree(hglobal)
			return False
		try:
			user32.EmptyClipboard()
			user32.SetClipboardData(CF_UNICODETEXT, hglobal)
		finally:
			user32.CloseClipboard()
		return True
	except Exception:
		return False


def send_enter_key(times: int = 1, delay: float = 0.08) -> bool:
	try:
		user32 = ctypes.windll.user32
		KEYEVENTF_KEYUP = 0x0002
		VK_RETURN = 0x0D

		for _ in range(max(1, int(times))):
			user32.keybd_event(VK_RETURN, 0, 0, 0)
			user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
			time.sleep(max(0.01, float(delay)))
		return True
	except Exception:
		return False


def paste_via_keyboard() -> bool:
	"""Simulate Ctrl+V for the focused window."""
	try:
		user32 = ctypes.windll.user32
		KEYEVENTF_KEYUP = 0x0002
		VK_CONTROL = 0x11
		VK_V = 0x56

		user32.keybd_event(VK_CONTROL, 0, 0, 0)
		user32.keybd_event(VK_V, 0, 0, 0)
		user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
		user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
		return True
	except Exception:
		return False


def paste_via_keyboard_and_enter() -> bool:
	"""Simulate Ctrl+V then Enter for focused window."""
	try:
		if not paste_via_keyboard():
			return False
		time.sleep(0.08)
		send_enter_key(times=2, delay=0.08)
		return True
	except Exception:
		return False

