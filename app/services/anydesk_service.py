"""AnyDesk connection service."""

import ctypes
import os
import subprocess
from pathlib import Path


def prepare_anydesk_conf(client_id: str):
	"""Write AnyDesk user.conf to enforce session defaults."""
	appdata = os.getenv("APPDATA")
	if not appdata:
		return
	anydesk_dir = os.path.join(appdata, "AnyDesk")
	Path(anydesk_dir).mkdir(parents=True, exist_ok=True)
	conf_file = os.path.join(anydesk_dir, "user.conf")
	try:
		with open(conf_file, "w", encoding="utf-8") as fw:
			fw.write(f"ad.session.viewmode={client_id}:2\n")
			fw.write("ad.installation.reminder_enabled=false\n")
			fw.write("ad.ui.inst_info_count=100\n")
			fw.write("ad.ui.last_reminder_time=1768860673\n")
			fw.write("ad.ui.install_skipped=true\n")
			fw.write("ad.features.install=false\n")
	except Exception:
		pass


def run_anydesk(exec_target: str, client_id, password):
	"""Launch AnyDesk connection flow using password pipe fallback."""
	prepare_anydesk_conf(client_id)

	try:
		if client_id:
			params = (
				f'/c echo {password} | "{exec_target}" "{client_id}" --with-password'
			)
		else:
			params = f'/c echo {password} | "{exec_target}" --with-password'
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)
		except Exception:
			command = (
				f'cmd /c echo {password} | "{exec_target}" "{client_id}" --with-password'
			)
			subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
	except Exception:
		try:
			cmd = [exec_target, str(client_id)] if client_id else [exec_target]
			subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
		except Exception:
			pass

