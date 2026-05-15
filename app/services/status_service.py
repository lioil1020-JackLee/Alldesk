"""Status polling and adapter service."""

import threading
import time

from app.services.status_manager import StatusManager


def get_rustdesk_peer_ids(read_clients_from_json, normalize_client_fields) -> list[str]:
	"""Build rustdesk peer id list from persisted clients."""
	try:
		clients = read_clients_from_json("rustdesk")
	except Exception:
		clients = []
	peer_ids: list[str] = []
	for c in clients:
		try:
			c = normalize_client_fields(c)
			pid = str(c.get("id", "") or "").strip()
		except Exception:
			pid = ""
		if pid:
			peer_ids.append(pid)
	return peer_ids


def restart_rustdesk_status_manager_from_config(
	current_manager,
	load_server_config,
	get_peer_ids,
):
	"""Create and start a new StatusManager based on persisted config."""
	cfg = load_server_config()
	host = str(cfg.get("server", "") or "").strip()
	try:
		api_port = int(cfg.get("rustdesk_api_port", 5014) or 5014)
	except Exception:
		api_port = 5014

	try:
		if current_manager is not None:
			current_manager.stop()
	except Exception:
		pass

	try:
		manager = StatusManager(
			host,
			api_port,
			timeout_s=5,
			interval_s=1,
			cache_grace_s=60,
			admin_online_window_s=45,
			status_change_confirm_polls=4,
			unknown_confirm_polls=20,
			min_state_hold_s=8,
			api_username=str(cfg.get("api_username", "") or ""),
			api_password=str(cfg.get("api_password", "") or ""),
		)
		manager.set_peer_ids(get_peer_ids())
		manager.start()
		return manager
	except Exception:
		return None


def compute_client_status(
	section: str,
	client: dict,
	normalize_client_fields,
	rustdesk_status_manager,
	ping_host,
	tcp_check,
) -> str:
	"""Compute current status color key for a client."""
	client = normalize_client_fields(client)
	try:
		client_id = str(client.get("id", "") or "").strip()
	except Exception:
		client_id = ""

	if section == "rustdesk":
		try:
			sm = rustdesk_status_manager
			if sm is None:
				return "error"
			online = sm.get_cached_status(client_id)
			if online is True:
				return "online"
			if online is False:
				return "offline"
			return "error"
		except Exception:
			return "error"

	if section == "anydesk":
		return "error"

	if section == "tightvnc":
		host = client_id
		if not host:
			return "error"
		try:
			port_s = str(client.get("port", "") or "").strip()
		except Exception:
			port_s = ""
		try:
			if port_s.isdigit():
				return "online" if tcp_check(host, int(port_s)) else "offline"
			return "online" if ping_host(host) else "offline"
		except Exception:
			return "error"

	return "error"


def refresh_status_once(
	gui,
	status_buttons,
	status_colors,
	read_clients_from_json,
	normalize_client_fields,
	rustdesk_status_manager,
	ping_host,
	tcp_check,
):
	"""Refresh all tracked button colors from latest status snapshot."""
	try:
		try:
			rustdesk_clients = read_clients_from_json("rustdesk")
		except Exception:
			rustdesk_clients = []
		try:
			anydesk_clients = read_clients_from_json("anydesk")
		except Exception:
			anydesk_clients = []
		try:
			tightvnc_clients = read_clients_from_json("tightvnc")
		except Exception:
			tightvnc_clients = []

		clients_by_section = {
			"rustdesk": rustdesk_clients,
			"anydesk": anydesk_clients,
			"tightvnc": tightvnc_clients,
		}

		for key, w in list(status_buttons.items()):
			try:
				section, tag, cid = key
			except Exception:
				continue
			try:
				btn = w.get("btn") if isinstance(w, dict) else None
				if not btn or not btn.winfo_exists():
					continue
			except Exception:
				continue

			clients = clients_by_section.get(section, [])

			target = None
			for c in clients:
				try:
					c = normalize_client_fields(c)
					if str(c.get("tag", "") or "").strip() == tag and str(
						c.get("id", "") or ""
					).strip() == cid:
						target = c
						break
				except Exception:
					continue

			if target is None:
				continue

			status = compute_client_status(
				section,
				target,
				normalize_client_fields,
				rustdesk_status_manager,
				ping_host,
				tcp_check,
			)
			color = status_colors.get(status, status_colors.get("error", "#666666"))

			def _apply(b=btn, c=color):
				try:
					b.configure(
						bg=c,
						activebackground=c,
						fg="#ffffff" if c != "#00cc66" else "#000000",
					)
				except Exception:
					pass

			try:
				gui.after(0, _apply)
			except Exception:
				pass
	except Exception:
		pass


def start_status_refresh_loop(refresh_once, interval: int = 1):
	"""Start daemon loop and periodically invoke refresh callback."""

	def _loop():
		while True:
			try:
				refresh_once()
			except Exception:
				pass
			time.sleep(interval)

	try:
		threading.Thread(target=_loop, daemon=True).start()
	except Exception:
		pass

