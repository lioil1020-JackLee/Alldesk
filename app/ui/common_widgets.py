"""Shared tkinter widget builders for Alldesk."""

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


def create_header_row(
	parent,
	*,
	on_connect,
	with_port=False,
	default_port="5900",
	section="",
	show_server_config=False,
	on_export=None,
	on_import=None,
	on_show_server_config=None,
):
	"""Build shared tab header with connect/csv/server-config controls."""
	header = ttk.Frame(parent)
	header.grid(row=0, column=0, columnspan=10, sticky="ew")
	try:
		header.columnconfigure(0, weight=1)
		header.columnconfigure(1, weight=0)
	except Exception:
		pass

	left_container = ttk.Frame(header)
	left_container.grid(row=0, column=0, sticky="w")

	right_container = None
	if section or show_server_config:
		right_container = ttk.Frame(header)
		right_container.grid(row=0, column=1, sticky="e")

	f_id = ttk.Frame(left_container)
	f_id.pack(side="left", padx=10)
	ttk.Label(f_id, text="連接ID:").pack(side="left")
	ent_id = tk.Entry(f_id, width=20)
	ent_id.pack(side="left", padx=6)

	f_pwd = ttk.Frame(left_container)
	f_pwd.pack(side="left", padx=10)
	ttk.Label(f_pwd, text="密碼:").pack(side="left")
	ent_pwd = tk.Entry(f_pwd, width=22)
	ent_pwd.pack(side="left", padx=6)

	ent_port = None

	def _on_click():
		on_connect(
			ent_id.get(),
			ent_pwd.get(),
			ent_port.get() if with_port and ent_port is not None else None,
		)

	btn = tk.Button(left_container, text="連接", command=_on_click)
	btn.pack(side="left", padx=6)

	if with_port:
		f_port = ttk.Frame(left_container)
		f_port.pack(side="left", padx=10)
		ttk.Label(f_port, text="埠:").pack(side="left")
		ent_port = tk.Entry(f_port, width=6)
		ent_port.pack(side="left", padx=6)
		ent_port.insert(0, default_port)

	if section and right_container:
		btn_export = tk.Button(
			right_container,
			text="匯出",
			command=(lambda: on_export(section)) if callable(on_export) else None,
			width=8,
		)
		btn_export.pack(side="left", padx=1)

		btn_import = tk.Button(
			right_container,
			text="匯入",
			command=(lambda: on_import(section)) if callable(on_import) else None,
			width=8,
		)
		btn_import.pack(side="left", padx=1)

	if show_server_config and right_container:
		btn_server = tk.Button(
			right_container,
			text="伺服器設定",
			command=on_show_server_config if callable(on_show_server_config) else None,
			width=10,
			bg="#2196F3",
			fg="white",
			font=("微軟正黑體", 9),
		)
		btn_server.pack(side="left", padx=1)

	return ent_id, ent_pwd, ent_port


def create_client_buttons(
	container,
	clients: list[dict],
	on_connect,
	*,
	section: str,
	status_buttons: dict,
	show_context_menu,
	normalize_client_fields,
	sanitize_tag,
	format_client_label_text,
	client_key,
	cols: int = 10,
	btn_font=("微軟正黑體", 10),
):
	"""Build client button grid and bind context-menu actions."""
	try:
		for k in list(status_buttons.keys()):
			if k and isinstance(k, tuple) and len(k) >= 1 and k[0] == section:
				status_buttons.pop(k, None)
	except Exception:
		pass

	btn_container = ttk.Frame(container)
	btn_container.grid(row=2, column=0, columnspan=10, sticky="ew")

	btn_container.bind(
		"<Button-3>",
		lambda e: show_context_menu(e, section, None, btn_container, on_connect),
	)
	container.bind(
		"<Button-3>",
		lambda e: show_context_menu(e, section, None, btn_container, on_connect),
	)

	row = 0
	col = 0

	if not clients:
		btn_container.configure(height=200)
		dummy_frame = tk.Frame(btn_container, height=200)
		dummy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
		dummy_frame.grid_propagate(False)
		dummy_frame.bind(
			"<Button-3>",
			lambda e: show_context_menu(e, section, None, btn_container, on_connect),
		)
	else:
		for client in clients:
			client = normalize_client_fields(client)
			try:
				tag = client.get("tag", "") or ""
			except Exception:
				tag = ""
			try:
				client_id = client.get("id", "") or ""
			except Exception:
				client_id = ""

			tag = sanitize_tag(tag)
			if isinstance(client_id, (int, float)):
				client_id = str(client_id)
			client_id = client_id.strip()
			if client_id.endswith(".0"):
				client_id = client_id[:-2]

			if isinstance(tag, str) and tag.strip().lower() in (
				"設備名稱",
				"id",
				"item",
				"name",
			):
				continue
			if isinstance(client_id, str) and client_id.strip().lower() in (
				"設備名稱",
				"id",
				"item",
				"name",
			):
				continue
			if not tag and not client_id:
				continue

			try:
				cell = tk.Frame(btn_container, bd=0, highlightthickness=0)
				cell.grid(row=row, column=col, padx=3, pady=3)

				btn = tk.Button(
					cell,
					text=format_client_label_text(tag, client_id),
					font=btn_font,
					width=15,
					height=3,
					command=(lambda c=client: on_connect(c)),
				)
				btn.pack(side="top")
				try:
					status_buttons[client_key(section, client)] = {
						"btn": btn,
						"cell": cell,
					}
				except Exception:
					pass

				btn.bind(
					"<Button-3>",
					lambda e, c=client: show_context_menu(
						e, section, c, btn_container, on_connect
					),
				)
				try:
					cell.bind(
						"<Button-3>",
						lambda e, c=client: show_context_menu(
							e, section, c, btn_container, on_connect
						),
					)
				except Exception:
					pass
			except Exception:
				pass

			col += 1
			if col >= cols:
				col = 0
				row += 1

	try:
		btn_container.grid_propagate(True)
	except Exception:
		pass

	try:
		container.update_idletasks()
	except Exception:
		pass

	return btn_container


def refresh_section_buttons(
	*,
	section: str,
	read_clients_from_json,
	create_client_buttons,
	rustdesk=None,
	anydesk=None,
	tightvnc=None,
):
	"""Rebuild one section's client grid and sync in-memory clients list."""
	clients = read_clients_from_json(section)

	global_instance = None
	if section == "rustdesk" and rustdesk is not None:
		rustdesk.clients = clients
		global_instance = rustdesk
	elif section == "anydesk" and anydesk is not None:
		anydesk.clients = clients
		global_instance = anydesk
	elif section == "tightvnc" and tightvnc is not None:
		tightvnc.clients = clients
		global_instance = tightvnc

	if global_instance and global_instance.btn_container:
		for widget in global_instance.btn_container.winfo_children():
			widget.destroy()

		if section == "rustdesk":
			global_instance.btn_container = create_client_buttons(
				global_instance.frame,
				global_instance.clients,
				lambda c: rustdesk.run_rustdesk_async(c.get("id"), c.get("pwd")),
				"rustdesk",
			)
		elif section == "anydesk":
			global_instance.btn_container = create_client_buttons(
				global_instance.frame,
				global_instance.clients,
				lambda c: anydesk.run_anydesk(c.get("id"), c.get("pwd")),
				"anydesk",
			)
		elif section == "tightvnc":
			global_instance.btn_container = create_client_buttons(
				global_instance.frame,
				global_instance.clients,
				lambda c: tightvnc.run_tightvnc(
					c.get("tag"), c.get("id"), c.get("pwd"), c.get("port")
				),
				"tightvnc",
				cols=10,
			)


def refresh_section_data(
	*,
	section: str,
	read_clients_from_json,
	create_client_buttons,
	rustdesk=None,
	anydesk=None,
	tightvnc=None,
	rustdesk_status_manager=None,
	get_rustdesk_peer_ids=None,
):
	"""Reload section data from json and rebuild UI for that section."""
	try:
		if section == "rustdesk" and rustdesk is not None:
			rustdesk.clients = read_clients_from_json("rustdesk")
			if rustdesk.btn_container:
				for widget in rustdesk.btn_container.winfo_children():
					widget.destroy()
			rustdesk.btn_container = create_client_buttons(
				rustdesk.frame,
				rustdesk.clients,
				lambda c: rustdesk.run_rustdesk_async(c.get("id"), c.get("pwd")),
				section,
			)
			try:
				if rustdesk_status_manager is not None and callable(get_rustdesk_peer_ids):
					rustdesk_status_manager.set_peer_ids(get_rustdesk_peer_ids())
			except Exception:
				pass
		elif section == "anydesk" and anydesk is not None:
			anydesk.clients = read_clients_from_json("anydesk")
			if anydesk.btn_container:
				for widget in anydesk.btn_container.winfo_children():
					widget.destroy()
			anydesk.btn_container = create_client_buttons(
				anydesk.frame,
				anydesk.clients,
				lambda c: anydesk.run_anydesk(c.get("id"), c.get("pwd")),
				section,
			)
		elif section == "tightvnc" and tightvnc is not None:
			tightvnc.clients = read_clients_from_json("tightvnc")
			if tightvnc.btn_container:
				for widget in tightvnc.btn_container.winfo_children():
					widget.destroy()
			tightvnc.btn_container = create_client_buttons(
				tightvnc.frame,
				tightvnc.clients,
				lambda c: tightvnc.run_tightvnc(
					c.get("tag"), c.get("id"), c.get("pwd"), c.get("port")
				),
				section,
				cols=10,
			)
	except Exception:
		pass


def import_csv_with_refresh(
	*,
	section: str,
	import_from_csv,
	refresh_section_data,
	log_and_show,
):
	"""Import one section from csv and refresh widgets when success."""
	if messagebox.askyesno(
		"確認匯入",
		f"確定要匯入資料到 {section} 區段嗎？\n這將覆蓋現有的 {section} 資料。",
	):
		if import_from_csv(section):
			refresh_section_data(section)
			log_and_show("匯入成功", f"{section} 資料已更新", "info")

