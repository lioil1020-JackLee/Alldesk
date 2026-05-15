"""JSON persistence for clients and server config."""

import json
import os
import stat
import tempfile
from pathlib import Path

from app.utils.paths import get_app_path, get_writable_dir


def get_default_server_config() -> dict:
	return {
		"server": "",
		"key": "",
		"rustdesk_api_port": 21114,
		"api_username": "",
		"api_password": "",
	}


def ensure_json_exists() -> bool:
	json_path = Path(get_app_path("Alldesk.json"))
	if json_path.exists():
		return True
	try:
		empty_data = {"rustdesk": [], "anydesk": [], "tightvnc": []}
		with open(json_path, "w", encoding="utf-8") as f:
			json.dump(empty_data, f, ensure_ascii=False, indent=2)
		return True
	except Exception:
		return False


def read_clients_from_json(section: str) -> list[dict]:
	if not ensure_json_exists():
		return []
	json_path = Path(get_app_path("Alldesk.json"))
	try:
		with open(json_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		return data.get(section, [])
	except Exception:
		return []


def dump_json_server_first(data: dict) -> str:
	try:
		if not isinstance(data, dict):
			return json.dumps(data, ensure_ascii=False, indent=2)
		if "server_config" in data:
			new = {"server_config": data["server_config"]}
			for k, v in data.items():
				if k == "server_config":
					continue
				new[k] = v
			return json.dumps(new, ensure_ascii=False, indent=2)
		return json.dumps(data, ensure_ascii=False, indent=2)
	except Exception:
		return json.dumps(data, ensure_ascii=False, indent=2)


def atomic_write_text(path: str, data: str, encoding: str = "utf-8") -> None:
	dirp = os.path.dirname(path) or get_writable_dir()
	fd = None
	tmp = None
	try:
		fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".tmp.", dir=dirp)
		with os.fdopen(fd, "w", encoding=encoding, newline="\n") as fw:
			fd = None
			fw.write(data)
			try:
				fw.flush()
				os.fsync(fw.fileno())
			except Exception:
				pass
		try:
			if os.path.exists(path):
				try:
					os.chmod(path, stat.S_IWRITE)
				except Exception:
					pass
		except Exception:
			pass
		os.replace(tmp, path)
		tmp = None
	finally:
		try:
			if fd is not None:
				try:
					os.close(fd)
				except Exception:
					pass
		except Exception:
			pass
		try:
			if tmp and os.path.exists(tmp):
				os.remove(tmp)
		except Exception:
			pass


def write_clients_to_json(section: str, clients: list[dict]) -> bool:
	json_path = Path(get_app_path("Alldesk.json"))
	data = {}
	if json_path.exists():
		try:
			with open(json_path, "r", encoding="utf-8") as f:
				data = json.load(f)
		except Exception:
			data = {}

	data[section] = clients
	try:
		atomic_write_text(str(json_path), dump_json_server_first(data), encoding="utf-8")
		return True
	except Exception:
		return False


def load_server_config() -> dict:
	if not ensure_json_exists():
		return get_default_server_config()

	json_path = Path(get_app_path("Alldesk.json"))
	try:
		with open(json_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		if "server_config" in data:
			cfg = data["server_config"] if isinstance(data["server_config"], dict) else {}
			server = str(
				cfg.get("server", "")
				or cfg.get("id_server", "")
				or cfg.get("relay_server", "")
			).strip()
			return {
				"server": server,
				"key": str(cfg.get("key", "") or ""),
				"rustdesk_api_port": int(cfg.get("rustdesk_api_port", 21114) or 21114),
				"api_username": str(cfg.get("api_username", "") or ""),
				"api_password": str(cfg.get("api_password", "") or ""),
			}
		return get_default_server_config()
	except Exception:
		return get_default_server_config()


def save_server_config(config: dict) -> bool:
	json_path = Path(get_app_path("Alldesk.json"))
	data = {}
	if json_path.exists():
		try:
			with open(json_path, "r", encoding="utf-8") as f:
				data = json.load(f)
		except Exception:
			data = {}
	data["server_config"] = config
	try:
		atomic_write_text(str(json_path), dump_json_server_first(data), encoding="utf-8")
		return True
	except Exception:
		return False

