"""RustDesk tab UI module."""

import ctypes
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from tkinter import ttk

class RustDesk:
	"""RustDesk tab UI and connection flow."""

	def __init__(
		self,
		notebook: ttk.Notebook,
		*,
		rustdesk_app: str,
		base_dir,
		exe_dir,
		get_app_path,
		resource_path,
		read_clients_from_json,
		load_server_config,
		atomic_write_text,
		launch_process,
		create_header_row,
		create_client_buttons,
		build_unilink_for_id,
		send_unilink_to_flutter_runner,
		find_window_for_id,
		is_rustdesk_id_not_found_dialog_open,
		is_rustdesk_connection_error_dialog_open,
		wait_and_input_password,
		try_focused_uia_password,
		close_window,
		send_unilink_via_copydata,
		try_uia_set_password,
		set_clipboard_text,
		paste_via_keyboard_and_enter,
		force_foreground,
	):
		self._rustdesk_app = rustdesk_app
		self._base_dir = base_dir
		self._exe_dir = exe_dir
		self._get_app_path = get_app_path
		self._resource_path = resource_path
		self._read_clients_from_json = read_clients_from_json
		self._load_server_config = load_server_config
		self._atomic_write_text = atomic_write_text
		self._launch_process = launch_process
		self._create_header_row = create_header_row
		self._create_client_buttons = create_client_buttons
		self._build_unilink_for_id = build_unilink_for_id
		self._send_unilink_to_flutter_runner = send_unilink_to_flutter_runner
		self._find_window_for_id = find_window_for_id
		self._is_rustdesk_id_not_found_dialog_open = (
			is_rustdesk_id_not_found_dialog_open
		)
		self._is_rustdesk_connection_error_dialog_open = (
			is_rustdesk_connection_error_dialog_open
		)
		self._wait_and_input_password = wait_and_input_password
		self._try_focused_uia_password = try_focused_uia_password
		self._close_window = close_window
		self._send_unilink_via_copydata = send_unilink_via_copydata
		self._try_uia_set_password = try_uia_set_password
		self._set_clipboard_text = set_clipboard_text
		self._paste_via_keyboard_and_enter = paste_via_keyboard_and_enter
		self._force_foreground = force_foreground
		self._password_watcher_stop = None
		self._password_watcher_lock = threading.Lock()
		self.init_rustdesk(notebook)

	def init_rustdesk(self, notebook: ttk.Notebook):
		try:
			app = os.getenv("RUSTDESK_APP")
			if not app:
				app = self._get_app_path(os.path.join("exe", "rustdesk.exe"))
			if not os.path.exists(app):
				if getattr(sys, "frozen", False):
					maybe = os.path.join(os.path.dirname(sys.executable), "rustdesk.exe")
					if os.path.exists(maybe):
						app = maybe
		except Exception:
			app = self._rustdesk_app

		clients = self._read_clients_from_json("rustdesk")
		self.exec_target = os.path.normpath(app)
		self.clients = clients
		self.frame = ttk.Frame(notebook)
		self.btn_container = None
		notebook.add(self.frame, text="RustDesk")

	def _prepare_rustdesk_conf(self, client_id: str, password: str):
		appdata = os.getenv("APPDATA")
		if not appdata:
			return
		cfg_dir = os.path.join(appdata, "RustDesk", "config")
		peers_dir = os.path.join(cfg_dir, "peers")
		Path(peers_dir).mkdir(parents=True, exist_ok=True)

		try:
			target_id = "" if client_id is None else str(client_id).strip()
		except Exception:
			target_id = ""
		if target_id.endswith(".0"):
			target_id = target_id[:-2]

		peer_file = os.path.join(peers_dir, f"{target_id}.toml")
		peer_content = (
			"password = []\n"
			"size = [\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"]\n"
			"size_ft = [\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"]\n"
			"size_pf = [\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"    0,\n"
			"]\n"
			"view_style = 'adaptive'\n"
			"scroll_style = 'scrollauto'\n"
			"edge_scroll_edge_thickness = 100\n"
			"image_quality = 'balanced'\n"
			"custom_image_quality = [50]\n"
			"show_remote_cursor = false\n"
			"lock_after_session_end = false\n"
			"terminal-persistent = false\n"
			"privacy_mode = false\n"
			"allow_swap_key = false\n"
			"port_forwards = []\n"
			"direct_failures = 1\n"
			"disable_audio = false\n"
			"disable_clipboard = false\n"
			"enable-file-copy-paste = true\n"
			"show_quality_monitor = false\n"
			"follow_remote_cursor = false\n"
			"follow_remote_window = false\n"
			"keyboard_mode = 'map'\n"
			"view_only = false\n"
			"show_my_cursor = false\n"
			"sync-init-clipboard = false\n"
			"trackpad-speed = 100\n\n"
			"[options]\n"
			"codec-preference = 'auto'\n"
			"swap-left-right-mouse = ''\n"
			"collapse_toolbar = ''\n"
			"custom-fps = '30'\n"
			"zoom-cursor = ''\n"
			"i444 = ''\n\n"
			"force-always-relay = 'Y'\n\n"
			"[ui_flutter]\n"
			'wm_RemoteDesktop = \'{"width":1270.0,"height":710.0,"offsetWidth":1270.0,"offsetHeight":710.0,"isMaximized":true,"isFullscreen":false}\'\n\n'
			"[info]\n"
			"username = 'VMM'\n"
			"hostname = 'soyal-pc'\n"
			"platform = 'Windows'\n\n"
			"[transfer]\n"
			"write_jobs = []\n"
			"read_jobs = []\n"
		)

		cfg_file = os.path.join(cfg_dir, "RustDesk2.toml")
		need_write_cfg = True
		if os.path.exists(cfg_file):
			try:
				with open(cfg_file, "r", encoding="utf-8") as fr:
					content = fr.read()
					server_config = self._load_server_config()
					server = server_config.get("server", "")
					if server and server in content:
						need_write_cfg = False
			except Exception:
				pass

		if need_write_cfg:
			server_config = self._load_server_config()
			server = server_config.get("server", "").strip()
			key = server_config.get("key", "").strip()

			try:
				if server and key:
					cfg_data = (
						f"rendezvous_server = '{server}:21116'\n"
						"nat_type = 1\n"
						"serial = 0\n"
						"unlock_pin = ''\n"
						"trusted_devices = ''\n\n"
						"[options]\n"
						f"relay-server = '{server}:21117'\n"
						f"custom-rendezvous-server = '{server}:21116'\n"
						"local-ip-addr = ''\n"
						f"key = '{key}'\n"
						"av1-test = 'Y'\n"
					)
				else:
					cfg_data = (
						"rendezvous_server = ''\n"
						"nat_type = 1\n"
						"serial = 0\n"
						"unlock_pin = ''\n"
						"trusted_devices = ''\n\n"
						"[options]\n"
						"relay-server = ''\n"
						"custom-rendezvous-server = ''\n"
						"local-ip-addr = ''\n"
						"key = ''\n"
						"av1-test = 'Y'\n"
					)

				tmp_cfg = cfg_file + ".tmp"
				try:
					with open(tmp_cfg, "w", encoding="utf-8", newline="\n") as fw:
						fw.write(cfg_data)
						try:
							fw.flush()
							os.fsync(fw.fileno())
						except Exception:
							pass
					os.replace(tmp_cfg, cfg_file)
				except Exception:
					try:
						if os.path.exists(cfg_file):
							os.remove(cfg_file)
						os.replace(tmp_cfg, cfg_file)
					except Exception:
						pass
			except Exception:
				pass

		try:
			if os.path.exists(peer_file):
				try:
					with open(peer_file, "r", encoding="utf-8") as fr:
						current = fr.read()
					if "view_style = 'adaptive'" in current:
						return
				except Exception:
					pass
		except Exception:
			pass

		try:
			self._atomic_write_text(peer_file, peer_content, encoding="utf-8")
		except Exception:
			pass

	def run_rustdesk_async(self, client_id, password):
		def _worker():
			try:
				self.run_rustdesk(client_id, password)
			except Exception:
				pass

		try:
			threading.Thread(target=_worker, daemon=True).start()
			return True
		except Exception:
			return self.run_rustdesk(client_id, password)

	def _foreground_title_for_client(self, client_id: str) -> str:
		try:
			user32 = ctypes.windll.user32
			hwnd = user32.GetForegroundWindow()
			if not hwnd:
				return ""
			buf = ctypes.create_unicode_buffer(1024)
			user32.GetWindowTextW(hwnd, buf, 1024)
			return (buf.value or "").strip()
		except Exception:
			return ""

	def _start_password_input_watcher(
		self,
		client_id: str,
		password: str,
		max_wait_time: float = 120.0,
	):
		try:
			with self._password_watcher_lock:
				if self._password_watcher_stop is not None:
					self._password_watcher_stop.set()
				stop_event = threading.Event()
				self._password_watcher_stop = stop_event
		except Exception:
			stop_event = threading.Event()

		result = {"ok": False, "saw": False}

		def _worker():
			start_time = time.time()
			deadline = time.time() + max_wait_time
			last_slow_fallback = 0.0
			try:
				while not stop_event.is_set() and time.time() < deadline:
					now = time.time()
					title = self._foreground_title_for_client(client_id)
					if str(client_id).strip() in title:
						try:
							ok, saw = self._try_focused_uia_password(str(password))
							if saw:
								result["saw"] = True
							if ok:
								result["ok"] = True
								break
						except Exception:
							pass
					try:
						if (
							self._is_rustdesk_id_not_found_dialog_open()
							or self._is_rustdesk_connection_error_dialog_open()
						):
							break
					except Exception:
						pass

					if (
						now - start_time >= 2.0
						and now - last_slow_fallback >= 1.0
					):
						last_slow_fallback = now
						try:
							ok, saw = self._wait_and_input_password(
								str(password), max_wait_time=0.05
							)
							if saw:
								result["saw"] = True
							if ok:
								result["ok"] = True
								break
						except Exception:
							pass

					stop_event.wait(0.03)
			finally:
				try:
					with self._password_watcher_lock:
						if self._password_watcher_stop is stop_event:
							self._password_watcher_stop = None
				except Exception:
					pass

		try:
			threading.Thread(target=_worker, daemon=True).start()
		except Exception:
			pass
		return result

	def _wait_for_password_watcher(self, result, max_wait_time: float = 25.0):
		deadline = time.time() + max_wait_time
		while time.time() < deadline:
			try:
				if result.get("ok"):
					return True, bool(result.get("saw"))
			except Exception:
				pass
			time.sleep(0.05)
		try:
			return bool(result.get("ok")), bool(result.get("saw"))
		except Exception:
			return False, False

	def run_rustdesk(self, client_id, password, _retried_no_password_dialog: bool = False):
		exec_target = self.exec_target

		try:
			if not exec_target or not os.path.exists(exec_target):
				candidates = []

				def _add_if_exists(p):
					try:
						if p and os.path.exists(p):
							candidates.append(p)
					except Exception:
						pass

				ordered_roots = []
				try:
					if getattr(sys, "frozen", False):
						exe_dir = os.path.dirname(sys.executable)
						ordered_roots = [
							os.path.join(exe_dir, "_internal", "exe"),
							os.path.join(exe_dir, "exe"),
							os.path.join(exe_dir, "_internal"),
							exe_dir,
						]
					else:
						ordered_roots = [
							os.path.join(str(self._base_dir), "_internal", "exe"),
							os.path.join(str(self._base_dir), "exe"),
							os.path.join(str(self._base_dir), "_internal"),
							str(self._base_dir),
						]
				except Exception:
					ordered_roots = [
						os.path.join(str(self._base_dir), "_internal", "exe"),
						os.path.join(str(self._base_dir), "exe"),
						str(self._base_dir),
					]

				for root in ordered_roots:
					try:
						_add_if_exists(os.path.join(root, "rustdesk.exe"))
						_add_if_exists(os.path.join(root, "RustDesk.exe"))
						if os.path.isdir(root):
							for fn in os.listdir(root):
								if fn.lower() == "rustdesk.exe":
									_add_if_exists(os.path.join(root, fn))
					except Exception:
						pass

				try:
					_add_if_exists(self._resource_path(os.path.join("_internal", "exe", "rustdesk.exe")))
					_add_if_exists(self._resource_path(os.path.join("exe", "rustdesk.exe")))
					_add_if_exists(self._get_app_path(os.path.join("_internal", "exe", "rustdesk.exe")))
					_add_if_exists(self._get_app_path(os.path.join("exe", "rustdesk.exe")))
				except Exception:
					pass

				try:
					_add_if_exists(os.getenv("RUSTDESK_APP"))
				except Exception:
					pass

				if candidates:
					exec_target = candidates[0]
		except Exception:
			pass

		self._prepare_rustdesk_conf(client_id, password)

		try:
			onefile_extracted = getattr(sys, "_MEIPASS", None) is not None
			should_copy = False
			if getattr(sys, "frozen", False) and not onefile_extracted:
				should_copy = True
			else:
				try:
					if exec_target and os.path.commonpath(
						[os.path.abspath(exec_target), str(self._exe_dir)]
					) == os.path.abspath(str(self._exe_dir)):
						should_copy = True
				except Exception:
					pass

			if should_copy and exec_target and os.path.exists(exec_target):
				try:
					tmp_name = f"rustdesk_{uuid.uuid4().hex}.exe"
					tmp_path = os.path.join(tempfile.gettempdir(), tmp_name)
					shutil.copy2(exec_target, tmp_path)
					os.chmod(
						tmp_path,
						os.stat(tmp_path).st_mode
						| stat.S_IREAD
						| stat.S_IWRITE
						| stat.S_IEXEC,
					)
					exec_target = tmp_path
				except Exception:
					pass
		except Exception:
			pass

		uni = self._build_unilink_for_id(client_id, password)
		cmd = [exec_target, "--connect", str(client_id)]
		password_watcher = self._start_password_input_watcher(str(client_id), str(password))
		try:
			proc = self._launch_process(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
		except Exception:
			proc = None

		id_not_found_abort = False
		process_failed_abort = False

		def _abort_wait_for_known_failures() -> bool:
			nonlocal id_not_found_abort, process_failed_abort
			try:
				if self._is_rustdesk_id_not_found_dialog_open():
					id_not_found_abort = True
					return True
				if self._is_rustdesk_connection_error_dialog_open():
					id_not_found_abort = True
					return True
			except Exception:
				pass
			try:
				if proc is not None:
					rc = proc.poll()
					if rc not in (None, 0):
						process_failed_abort = True
						return True
			except Exception:
				pass
			return False

		hwnd = self._find_window_for_id(
			str(client_id),
			timeout=2.0,
			abort_if=_abort_wait_for_known_failures,
		)
		initial_found = bool(hwnd)

		try:
			if hwnd:
				try:
					user32 = __import__("ctypes").windll.user32
					SW_MAXIMIZE = 3
					user32.ShowWindow(hwnd, SW_MAXIMIZE)
					try:
						user32.SetForegroundWindow(hwnd)
						user32.BringWindowToTop(hwnd)
					except Exception:
						pass
				except Exception:
					pass
		except Exception:
			pass

		if not hwnd:
			if id_not_found_abort or process_failed_abort:
				return False
			try:
				self._launch_process(
					[exec_target, "--connect", str(client_id)],
					creationflags=subprocess.CREATE_NEW_CONSOLE,
				)
				password_ok, saw_pwd_dialog = self._wait_for_password_watcher(
					password_watcher, max_wait_time=25.0
				)
				if password_ok:
					return True
				hwnd = self._find_window_for_id(str(client_id), timeout=3.0)
				initial_found = bool(hwnd)
				if not hwnd:
					return True
			except Exception:
				return False

		try:
			if self._send_unilink_to_flutter_runner(uni):
				hwnd2 = (
					hwnd
					if initial_found
					else self._find_window_for_id(str(client_id), timeout=2.0)
				)
				if hwnd2:
					try:
						self._force_foreground(hwnd2)
						time.sleep(0.08)
					except Exception:
						pass
				password_ok, saw_pwd_dialog = self._wait_for_password_watcher(
					password_watcher, max_wait_time=25.0
				)
				if password_ok:
					return True
		except Exception:
			pass

		try:
			if self._send_unilink_via_copydata(hwnd, uni):
				password_ok, saw_pwd_dialog = self._wait_for_password_watcher(
					password_watcher, max_wait_time=25.0
				)
				if password_ok:
					return True

				if (not saw_pwd_dialog) and (not _retried_no_password_dialog):
					try:
						self._close_window(hwnd)
					except Exception:
						pass
					time.sleep(0.2)
					return self.run_rustdesk(
						client_id,
						password,
						_retried_no_password_dialog=True,
					)

				try:
					if self._try_uia_set_password(hwnd, str(password)):
						return True
				except Exception:
					pass

				try:
					if self._set_clipboard_text(str(password)):
						time.sleep(0.12)
						if self._paste_via_keyboard_and_enter():
							return True
				except Exception:
					pass
				return True
		except Exception:
			pass

		if not (locals().get("initial_found") or False):
			try:
				self._launch_process(
					[exec_target, "--connect", str(client_id)],
					creationflags=subprocess.CREATE_NEW_CONSOLE,
				)
				self._wait_for_password_watcher(password_watcher, max_wait_time=25.0)
				return True
			except Exception:
				pass

		return True

	def set_elements_rustdesk(self):
		self._create_header_row(
			self.frame,
			on_connect=lambda cid, pwd, _: self.run_rustdesk_async(cid, pwd),
			with_port=False,
			section="rustdesk",
			show_server_config=True,
		)
		self.btn_container = self._create_client_buttons(
			self.frame,
			self.clients,
			lambda c: self.run_rustdesk_async(c.get("id"), c.get("pwd")),
			"rustdesk",
		)

