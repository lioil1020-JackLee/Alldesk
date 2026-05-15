"""Text normalization and sanitization helpers."""


def client_key(section: str, client: dict) -> tuple:
	"""Build stable key for UI button state lookup."""
	try:
		tag = str(client.get("tag", "") or "").strip()
	except Exception:
		tag = ""
	try:
		cid = str(client.get("id", "") or "").strip()
	except Exception:
		cid = ""
	return (section, tag, cid)


def format_client_label_text(tag: str, client_id: str) -> str:
	"""Format two-line client label text for button captions."""
	tag = tag or ""
	client_id = client_id or ""
	if tag and client_id:
		return f"{tag}\n{client_id}"
	if tag and not client_id:
		return f"{tag}"
	if client_id and not tag:
		return f"{client_id}"
	return ""


def sanitize_tag(s: str) -> str:
	"""Filter suspicious or malformed tag text before showing in UI."""
	if not isinstance(s, str):
		return ""
	v = s.strip()
	if not v:
		return ""
	low = v.lower()
	suspicious = (
		"import ",
		"def ",
		"class ",
		"shutil",
		"tkinter",
		"pyinstaller",
		"from ",
		"subprocess",
	)
	if any(tok in low for tok in suspicious):
		return ""
	if len(v) > 128:
		return ""
	non_print = sum(1 for ch in v if not ch.isprintable())
	if non_print > max(1, len(v) // 10):
		return ""
	return v


def normalize_client_fields(client: dict) -> dict:
	"""Normalize client dict fields and convert common malformed values."""
	out = {"tag": "", "id": "", "pwd": "", "port": ""}
	if not isinstance(client, dict):
		return out
	try:
		tag = client.get("tag", "") or ""
		id_ = client.get("id", "") if client.get("id", "") is not None else ""
		pwd = client.get("pwd", "") or ""
		port = client.get("port", "") if client.get("port", "") is not None else ""
	except Exception:
		return out

	try:
		if isinstance(id_, (int, float)):
			id_ = str(id_)
		id_ = str(id_).strip()
		if id_.endswith(".0"):
			id_ = id_[:-2]
	except Exception:
		id_ = ""

	try:
		tag = str(tag).strip()
	except Exception:
		tag = ""

	try:
		pwd = str(pwd).strip()
	except Exception:
		pwd = ""

	try:
		if isinstance(port, (int, float)):
			port = str(int(port))
		else:
			port = str(port).strip()
			if port.endswith(".0"):
				port = port[:-2]
	except Exception:
		port = ""

	out["tag"] = tag
	out["id"] = id_
	out["pwd"] = pwd
	out["port"] = port
	return out

