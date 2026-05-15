"""AnyDesk tab UI module."""

import os
from tkinter import ttk

from app.services import anydesk_service


class AnyDesk:
	"""AnyDesk tab UI and interactions."""

	def __init__(
		self,
		notebook: ttk.Notebook,
		*,
		anydesk_app: str,
		read_clients_from_json,
		create_header_row,
		create_client_buttons,
	):
		self._read_clients_from_json = read_clients_from_json
		self._create_header_row = create_header_row
		self._create_client_buttons = create_client_buttons
		self._anydesk_app = anydesk_app
		self.init_anydesk(notebook)

	def init_anydesk(self, notebook: ttk.Notebook):
		app = self._anydesk_app
		clients = self._read_clients_from_json("anydesk")
		exec_target = os.path.normpath(app)

		self.exec_target = exec_target
		self.clients = clients
		self.frame = ttk.Frame(notebook)
		self.btn_container = None
		notebook.add(self.frame, text="AnyDesk")

	def _prepare_anydesk_conf(self, client_id: str):
		anydesk_service.prepare_anydesk_conf(client_id)

	def run_anydesk(self, client_id, password):
		anydesk_service.run_anydesk(self.exec_target, client_id, password)

	def set_elements_anydesk(self):
		self._create_header_row(
			self.frame,
			on_connect=lambda cid, pwd, _: self.run_anydesk(cid, pwd),
			with_port=False,
			section="anydesk",
		)
		self.btn_container = self._create_client_buttons(
			self.frame,
			self.clients,
			lambda c: self.run_anydesk(c.get("id"), c.get("pwd")),
			"anydesk",
		)

