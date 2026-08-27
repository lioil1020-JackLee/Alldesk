"""Dialog windows for Alldesk."""

import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from app.utils.text import status_check_enabled


def show_client_context_menu(
	event,
	*,
	container,
	client,
	on_edit,
	on_delete,
	on_add,
):
	"""Show right-click menu for add/edit/delete client actions."""
	context_menu = tk.Menu(container, tearoff=0)
	try:
		menu_font = tkfont.Font(family="微軟正黑體", size=16)
		context_menu.configure(font=menu_font)
	except Exception:
		pass

	if client is not None:
		context_menu.add_command(label="編輯客戶", command=on_edit)
		try:
			context_menu.add_separator()
		except Exception:
			pass
		context_menu.add_command(label="刪除客戶", command=on_delete)
		context_menu.add_separator()

	context_menu.add_command(label="新增客戶", command=on_add)

	try:
		context_menu.tk_popup(event.x_root, event.y_root)
	finally:
		context_menu.grab_release()


def edit_client_dialog(
	*,
	gui,
	section: str,
	client: dict,
	container,
	on_connect,
	read_clients_from_json,
	write_clients_to_json,
	refresh_section_buttons,
	delete_client,
	log_and_show,
):
	"""Open add/edit client dialog and persist changes via callbacks."""
	is_new = not client.get("tag") and not client.get("id")
	title = f"新增 {section} 客戶" if is_new else f"編輯 {section} 客戶"

	dialog = tk.Toplevel(gui)
	try:
		dialog.withdraw()
	except Exception:
		pass
	dialog.title(title)
	dialog.resizable(True, True)
	dialog.minsize(520, 360)
	try:
		dialog.transient(gui)
	except Exception:
		pass

	title_label = tk.Label(dialog, text=title, font=("微軟正黑體", 12, "bold"))
	title_label.grid(row=0, column=0, columnspan=2, pady=(10, 20))

	separator1 = ttk.Separator(dialog, orient="horizontal")
	separator1.grid(row=1, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 5))

	input_frame = tk.Frame(dialog)
	input_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=30, pady=5)

	tag_frame = tk.Frame(input_frame)
	tag_frame.pack(fill="x", pady=(5, 10))
	tk.Label(
		tag_frame,
		text="設備名稱:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	).pack(side="left")
	tag_entry = tk.Entry(tag_frame, width=40, font=("微軟正黑體", 10))
	tag_entry.insert(0, client.get("tag", ""))
	tag_entry.pack(side="left", fill="x", expand=True)

	id_frame = tk.Frame(input_frame)
	id_frame.pack(fill="x", pady=10)
	tk.Label(
		id_frame,
		text="連線 ID:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	).pack(side="left")
	id_entry = tk.Entry(id_frame, width=40, font=("微軟正黑體", 10))
	id_entry.insert(0, client.get("id", ""))
	id_entry.pack(side="left", fill="x", expand=True)

	pwd_frame = tk.Frame(input_frame)
	pwd_frame.pack(fill="x", pady=10)
	tk.Label(
		pwd_frame,
		text="密碼:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	).pack(side="left")
	pwd_entry = tk.Entry(pwd_frame, width=40, font=("微軟正黑體", 10))
	pwd_entry.insert(0, client.get("pwd", ""))
	pwd_entry.pack(side="left", fill="x", expand=True)

	port_frame = tk.Frame(input_frame)
	port_frame.pack(fill="x", pady=(10, 5))
	tk.Label(
		port_frame,
		text="埠號:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	).pack(side="left")
	port_entry = tk.Entry(port_frame, width=40, font=("微軟正黑體", 10))
	port_entry.insert(0, client.get("port", ""))
	port_entry.pack(side="left", fill="x", expand=True)

	check_status_var = tk.BooleanVar(value=status_check_enabled(client))
	if section == "rustdesk":
		check_status_frame = tk.Frame(input_frame)
		check_status_frame.pack(fill="x", pady=(8, 5))
		tk.Label(
			check_status_frame,
			text="\u67e5\u8a62\u72c0\u614b:",
			font=("Microsoft JhengHei UI", 11, "bold"),
			width=12,
			anchor="w",
		).pack(side="left")
		tk.Checkbutton(
			check_status_frame,
			text="\u555f\u7528",
			variable=check_status_var,
		).pack(side="left")

	separator2 = ttk.Separator(dialog, orient="horizontal")
	separator2.grid(row=3, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 20))

	def save_changes():
		updated_client = {
			"tag": tag_entry.get().strip(),
			"id": id_entry.get().strip(),
			"pwd": pwd_entry.get().strip(),
			"port": port_entry.get().strip(),
		}
		if section == "rustdesk":
			updated_client["check_status"] = bool(check_status_var.get())

		if not updated_client["tag"] and not updated_client["id"]:
			delete_client(section, client, container, on_connect)
			dialog.destroy()
			return

		clients = read_clients_from_json(section)
		local_is_new = not client.get("tag") and not client.get("id")

		if local_is_new:
			clients.append(updated_client)
		else:
			updated = False
			for i, c in enumerate(clients):
				if (
					c.get("tag") == client.get("tag")
					and c.get("id") == client.get("id")
					and c.get("pwd") == client.get("pwd")
				):
					clients[i] = updated_client
					updated = True
					break
			if not updated:
				clients.append(updated_client)

		if write_clients_to_json(section, clients):
			refresh_section_buttons(section, container, on_connect)
			action = "新增" if local_is_new else "編輯"
			log_and_show("成功", f"{section} 客戶已{action}", "info")
			dialog.destroy()
		else:
			log_and_show("儲存失敗", "更新資料時發生錯誤", "error")

	button_container = tk.Frame(dialog)
	button_container.grid(
		row=4, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 20)
	)
	button_inner = tk.Frame(button_container)
	button_inner.pack(anchor="center")

	button_style = {
		"font": ("微軟正黑體", 11),
		"width": 15,
		"height": 2,
		"relief": "raised",
		"bd": 2,
		"cursor": "hand2",
	}

	save_btn = tk.Button(
		button_inner,
		text="儲存",
		bg="#4CAF50",
		fg="white",
		command=save_changes,
		**button_style,
	)
	save_btn.pack(side="left", padx=15, ipady=5, ipadx=10)

	cancel_btn = tk.Button(
		button_inner,
		text="取消",
		bg="#f44336",
		fg="white",
		command=dialog.destroy,
		**button_style,
	)
	cancel_btn.pack(side="left", padx=15, ipady=5, ipadx=10)

	try:
		try:
			dialog.update_idletasks()
		except Exception:
			pass

		def _center_dialog():
			try:
				req_w = dialog.winfo_reqwidth()
				req_h = dialog.winfo_reqheight()
				width = max(req_w, 520)
				height = max(req_h, 360)
				try:
					screen_width = gui.winfo_screenwidth()
					screen_height = gui.winfo_screenheight()
				except Exception:
					screen_width = dialog.winfo_screenwidth()
					screen_height = dialog.winfo_screenheight()

				dx = max((screen_width - width) // 2, 0)
				dy = max((screen_height - height) // 2, 0)
				dialog.geometry(f"{width}x{height}+{dx}+{dy}")
				try:
					dialog.deiconify()
				except Exception:
					pass
				try:
					dialog.grab_set()
				except Exception:
					pass
				try:
					dialog.focus_force()
				except Exception:
					pass
				dialog.lift()
				dialog.attributes("-topmost", True)
				dialog.after(200, lambda: dialog.attributes("-topmost", False))
			except Exception:
				try:
					dialog.geometry("520x360+100+100")
				except Exception:
					pass

		_center_dialog()
		dialog.after(80, _center_dialog)
		dialog.after(300, _center_dialog)
	except Exception:
		try:
			dialog.geometry("520x360+100+100")
		except Exception:
			pass


def show_server_config_dialog(
	*,
	gui,
	load_server_config,
	save_server_config,
	log_and_show,
	on_config_saved,
	on_restart_status_manager,
	icon_candidates,
):
	"""Open RustDesk server config dialog and persist settings."""
	dialog = tk.Toplevel(gui)
	try:
		dialog.withdraw()
	except Exception:
		pass
	dialog.title("伺服器設定")
	dialog.resizable(True, True)
	dialog.minsize(520, 360)

	try:
		icon_path = next((p for p in icon_candidates if p and os.path.exists(p)), None)
		if icon_path:
			try:
				dialog.iconbitmap(icon_path)
			except Exception:
				try:
					img = tk.PhotoImage(file=icon_path)
					dialog.iconphoto(False, img)
				except Exception:
					pass
	except Exception:
		pass

	try:
		dialog.transient(gui)
	except Exception:
		pass

	current_config = load_server_config()

	title_label = tk.Label(
		dialog, text="RustDesk 伺服器設定", font=("微軟正黑體", 12, "bold")
	)
	title_label.grid(row=0, column=0, columnspan=2, pady=(10, 20))

	separator1 = ttk.Separator(dialog, orient="horizontal")
	separator1.grid(row=1, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 5))

	input_frame = tk.Frame(dialog)
	input_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=30, pady=5)

	server_frame = tk.Frame(input_frame)
	server_frame.pack(fill="x", pady=(5, 10))
	tk_server = tk.Label(
		server_frame,
		text="伺服器:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	)
	tk_server.pack(side="left")
	server_entry = tk.Entry(server_frame, width=40, font=("微軟正黑體", 10))
	server_entry.insert(0, current_config.get("server", ""))
	server_entry.pack(side="left", fill="x", expand=True)

	key_frame = tk.Frame(input_frame)
	key_frame.pack(fill="x", pady=(10, 5))
	tk_key = tk.Label(
		key_frame, text="Key:", font=("微軟正黑體", 11, "bold"), width=8, anchor="w"
	)
	tk_key.pack(side="left")
	key_entry = tk.Entry(key_frame, width=40, font=("微軟正黑體", 10))
	key_entry.insert(0, current_config.get("key", ""))
	key_entry.pack(side="left", fill="x", expand=True)

	api_port_frame = tk.Frame(input_frame)
	api_port_frame.pack(fill="x", pady=(10, 5))
	tk_api_port = tk.Label(
		api_port_frame,
		text="API埠:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	)
	tk_api_port.pack(side="left")
	api_port_entry = tk.Entry(api_port_frame, width=40, font=("微軟正黑體", 10))
	try:
		api_port_entry.insert(0, str(int(current_config.get("rustdesk_api_port", 21114))))
	except Exception:
		api_port_entry.insert(0, "21114")
	api_port_entry.pack(side="left", fill="x", expand=True)

	separator2 = ttk.Separator(dialog, orient="horizontal")
	separator2.grid(row=3, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 20))

	api_user_frame = tk.Frame(input_frame)
	api_user_frame.pack(fill="x", pady=(10, 5))
	tk_api_user = tk.Label(
		api_user_frame,
		text="API帳號:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	)
	tk_api_user.pack(side="left")
	api_user_entry = tk.Entry(api_user_frame, width=40, font=("微軟正黑體", 10))
	api_user_entry.insert(0, current_config.get("api_username", ""))
	api_user_entry.pack(side="left", fill="x", expand=True)

	api_pass_frame = tk.Frame(input_frame)
	api_pass_frame.pack(fill="x", pady=(10, 5))
	tk_api_pass = tk.Label(
		api_pass_frame,
		text="API密碼:",
		font=("微軟正黑體", 11, "bold"),
		width=8,
		anchor="w",
	)
	tk_api_pass.pack(side="left")
	api_pass_entry = tk.Entry(api_pass_frame, width=40, font=("微軟正黑體", 10), show="*")
	api_pass_entry.insert(0, current_config.get("api_password", ""))
	api_pass_entry.pack(side="left", fill="x", expand=True)

	def toggle_api_password_visibility():
		if api_pass_entry.cget("show") == "":
			api_pass_entry.config(show="*")
		else:
			api_pass_entry.config(show="")
		api_pass_entry.focus_set()

	api_pass_toggle_btn = tk.Button(
		api_pass_frame,
		text="👁",
		font=("微軟正黑體", 10),
		width=3,
		command=toggle_api_password_visibility,
	)
	api_pass_toggle_btn.pack(side="left", padx=(8, 0))

	def save_config():
		port_s = api_port_entry.get().strip()
		if not port_s.isdigit():
			log_and_show("儲存失敗", "API埠必須是數字", "error")
			return
		port_v = int(port_s)
		if port_v <= 0 or port_v > 65535:
			log_and_show("儲存失敗", "API埠範圍必須是 1~65535", "error")
			return

		new_config = {
			"server": server_entry.get().strip(),
			"key": key_entry.get().strip(),
			"rustdesk_api_port": port_v,
			"api_username": api_user_entry.get().strip(),
			"api_password": api_pass_entry.get(),
		}

		if not new_config["server"] or not new_config["key"]:
			log_and_show("儲存失敗", "所有欄位都必須填寫", "error")
			return

		if save_server_config(new_config):
			try:
				on_config_saved(dict(new_config))
			except Exception:
				pass
			try:
				on_restart_status_manager()
			except Exception:
				pass
			log_and_show("儲存成功", "伺服器設定已更新", "info")
			dialog.destroy()
		else:
			log_and_show("儲存失敗", "更新伺服器設定時發生錯誤", "error")

	button_container = tk.Frame(dialog)
	button_container.grid(
		row=4, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 20)
	)
	button_inner = tk.Frame(button_container)
	button_inner.pack(anchor="center")

	button_style = {
		"font": ("微軟正黑體", 11),
		"width": 15,
		"height": 2,
		"relief": "raised",
		"bd": 2,
		"cursor": "hand2",
	}

	save_btn = tk.Button(
		button_inner,
		text="儲存",
		bg="#4CAF50",
		fg="white",
		command=save_config,
		**button_style,
	)
	save_btn.pack(side="left", padx=15, ipady=5, ipadx=10)

	cancel_btn = tk.Button(
		button_inner,
		text="取消",
		bg="#f44336",
		fg="white",
		command=dialog.destroy,
		**button_style,
	)
	cancel_btn.pack(side="left", padx=15, ipady=5, ipadx=10)

	try:
		try:
			dialog.update_idletasks()
		except Exception:
			pass

		def _center_dialog():
			try:
				req_w = dialog.winfo_reqwidth()
				req_h = dialog.winfo_reqheight()
				width = max(req_w, 520)
				height = max(req_h, 360)
				try:
					screen_width = gui.winfo_screenwidth()
					screen_height = gui.winfo_screenheight()
				except Exception:
					screen_width = dialog.winfo_screenwidth()
					screen_height = dialog.winfo_screenheight()

				dx = max((screen_width - width) // 2, 0)
				dy = max((screen_height - height) // 2, 0)
				dialog.geometry(f"{width}x{height}+{dx}+{dy}")
				try:
					dialog.deiconify()
				except Exception:
					pass
				try:
					dialog.grab_set()
				except Exception:
					pass
				try:
					dialog.focus_force()
				except Exception:
					pass
				dialog.lift()
				dialog.attributes("-topmost", True)
				dialog.after(200, lambda: dialog.attributes("-topmost", False))
			except Exception:
				try:
					dialog.geometry("520x360+100+100")
				except Exception:
					pass

		_center_dialog()
		dialog.after(80, _center_dialog)
		dialog.after(300, _center_dialog)
	except Exception:
		try:
			dialog.geometry("520x360+100+100")
		except Exception:
			pass

