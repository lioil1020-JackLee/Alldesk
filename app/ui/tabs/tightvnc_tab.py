"""TightVNC tab UI module."""

from tkinter import ttk

from app.services import tightvnc_service


class TightVNC:
	"""TightVNC tab UI and interactions."""

	def __init__(
		self,
		notebook: ttk.Notebook,
		*,
		tightvnc_app: str,
		exe_dir,
		read_clients_from_json,
		create_header_row,
		create_client_buttons,
		resource_path,
		encrypt_tightvnc_password,
		get_writable_dir,
	):
		self._read_clients_from_json = read_clients_from_json
		self._create_header_row = create_header_row
		self._create_client_buttons = create_client_buttons
		self._resource_path = resource_path
		self._encrypt_tightvnc_password = encrypt_tightvnc_password
		self._get_writable_dir = get_writable_dir
		self._tightvnc_app = tightvnc_app
		self._exe_dir = exe_dir
		self.init_tightvnc(notebook)

	def init_tightvnc(self, notebook: ttk.Notebook):
		clients = self._read_clients_from_json("tightvnc")
		self.exec_target = self._tightvnc_app
		self.clients = clients
		self.frame = ttk.Frame(notebook)
		self.btn_container = None
		notebook.add(self.frame, text="TightVNC")

	def _prepare_and_launch_tightvnc(self, host, port, password):
		tightvnc_service.prepare_and_launch_tightvnc(
			host,
			port,
			password,
			self._resource_path,
			self._exe_dir,
			self._tightvnc_app,
			self._encrypt_tightvnc_password,
			self._get_writable_dir,
		)

	def run_tightvnc(self, item, url, password, port):
		tightvnc_service.run_tightvnc(
			url,
			password,
			port,
			self._resource_path,
			self._exe_dir,
			self._tightvnc_app,
			self._encrypt_tightvnc_password,
			self._get_writable_dir,
		)

	def set_elements_tightvnc(self):
		self._create_header_row(
			self.frame,
			on_connect=lambda cid, pwd, port: self.run_tightvnc("", cid, pwd, port),
			with_port=True,
			default_port="5900",
			section="tightvnc",
		)
		self.btn_container = self._create_client_buttons(
			self.frame,
			self.clients,
			lambda c: self.run_tightvnc(
				c.get("tag"), c.get("id"), c.get("pwd"), c.get("port")
			),
			"tightvnc",
			cols=10,
		)

