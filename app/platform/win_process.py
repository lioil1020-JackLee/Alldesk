"""Windows process launch helpers."""

import subprocess

from app.utils.paths import get_writable_dir


def launch_process(cmd, cwd=None, creationflags=0, timeout=None, stdout=None, stderr=None):
	"""Launch external process and return Popen object, or None on failure."""
	try:
		proc = subprocess.Popen(
			cmd,
			cwd=cwd or get_writable_dir(),
			creationflags=creationflags,
			stdout=stdout,
			stderr=stderr,
		)
		return proc
	except Exception:
		return None

