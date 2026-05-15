"""TightVNC connection service."""

import os
import subprocess
from pathlib import Path


def prepare_and_launch_tightvnc(
	host,
	port,
	password,
	resource_path,
	exe_dir,
	tightvnc_app,
	encrypt_tightvnc_password,
	get_writable_dir,
):
	"""Build vnc options file then launch TightVNC."""
	vnc_source = resource_path("vnc.vnc")
	if os.path.exists(vnc_source):
		try:
			with open(vnc_source, "r", encoding="utf-8") as f:
				lines = f.readlines()
		except Exception:
			lines = []
	else:
		lines = []

	out = []
	in_conn = False
	replaced = {"host": False, "port": False, "password": False}
	for line in lines:
		s = line.strip()
		if s.lower() == "[connection]":
			in_conn = True
			out.append(line)
			continue
		if in_conn:
			if s.startswith("[") and s.endswith("]"):
				in_conn = False
				out.append(line)
				continue
			if s.lower().startswith("host="):
				out.append(f"host={host}\n")
				replaced["host"] = True
				continue
			if s.lower().startswith("port="):
				out.append(f"port={port}\n")
				replaced["port"] = True
				continue
			if s.lower().startswith("password="):
				if password:
					enc_pw = encrypt_tightvnc_password(password)
					out.append(f"password={enc_pw}\n")
					replaced["password"] = True
				else:
					out.append(line)
				continue
		out.append(line)

	if not any(l.strip().lower() == "[connection]" for l in out):
		conn_block = ["[connection]\n", f"host={host}\n", f"port={port}\n"]
		if password:
			enc_pw = encrypt_tightvnc_password(password)
			conn_block.append(f"password={enc_pw}\n")
		out = conn_block + ["\n"] + out

	try:
		Path(exe_dir).mkdir(parents=True, exist_ok=True)
	except Exception:
		pass

	out_path = os.path.join(str(exe_dir), "vnc.vnc")
	try:
		with open(out_path, "w", encoding="utf-8") as f:
			f.writelines(out)
	except Exception:
		return

	exe_path = resource_path("TightVNC.exe")
	if not os.path.exists(exe_path):
		exe_path = tightvnc_app
	if not os.path.exists(exe_path):
		exe_path = "TightVNC.exe"

	args = [exe_path, f"-optionsfile={out_path}", "-showcontrols=no"]
	try:
		subprocess.Popen(args, cwd=get_writable_dir())
	except Exception:
		pass


def run_tightvnc(
	url,
	password,
	port,
	resource_path,
	exe_dir,
	tightvnc_app,
	encrypt_tightvnc_password,
	get_writable_dir,
):
	"""High-level TightVNC launcher."""
	host = url or ""
	prt = port or "5900"
	prepare_and_launch_tightvnc(
		host,
		prt,
		password,
		resource_path,
		exe_dir,
		tightvnc_app,
		encrypt_tightvnc_password,
		get_writable_dir,
	)

