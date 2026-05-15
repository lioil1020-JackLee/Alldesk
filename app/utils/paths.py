"""Application path helpers."""

import os
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
EXE_DIR = BASE_DIR / "exe"
VNC_BASE_DIR = getattr(sys, "_MEIPASS", None) or str(BASE_DIR)


def resource_path(filename: str) -> str:
	"""Resolve resource file path for dev mode and PyInstaller bundles."""
	meipass = getattr(sys, "_MEIPASS", None)
	if meipass:
		return os.path.join(meipass, filename)
	return os.path.join(VNC_BASE_DIR, filename)


def get_app_path(filename: str) -> str:
	"""Resolve app-relative writable path for frozen and source runs."""
	try:
		if getattr(sys, "frozen", False):
			return os.path.join(os.path.dirname(sys.executable), filename)
	except Exception:
		pass
	return os.path.join(str(BASE_DIR), filename)


def get_writable_dir() -> str:
	"""Return a writable directory for current runtime mode."""
	if getattr(sys, "frozen", False):
		return tempfile.gettempdir()
	return str(BASE_DIR)

