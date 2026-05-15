"""CSV import/export repository helpers."""

import csv

from app.repositories.json_repo import read_clients_from_json, write_clients_to_json


def export_to_csv(section: str, file_path: str) -> tuple[bool, str]:
	"""Export section data to csv file path."""
	clients = read_clients_from_json(section)
	if not clients:
		return False, "no_data"

	try:
		with open(file_path, "w", newline="", encoding="utf-8-sig") as csvfile:
			fieldnames = ["tag", "id", "pwd", "port"]
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			writer.writeheader()
			for client in clients:
				row = {
					"tag": client.get("tag", ""),
					"id": client.get("id", ""),
					"pwd": client.get("pwd", ""),
					"port": client.get("port", ""),
				}
				writer.writerow(row)
		return True, str(len(clients))
	except Exception as e:
		return False, str(e)


def import_from_csv(section: str, file_path: str) -> tuple[bool, str]:
	"""Import csv data into given section."""
	try:
		clients = []
		with open(file_path, "r", encoding="utf-8-sig") as csvfile:
			reader = csv.DictReader(csvfile)
			for row in reader:
				client = {
					"tag": row.get("tag", "").strip(),
					"id": row.get("id", "").strip(),
					"pwd": row.get("pwd", "").strip(),
					"port": row.get("port", "").strip(),
				}
				if client["tag"] or client["id"]:
					clients.append(client)

		if not clients:
			return False, "no_valid_data"

		if write_clients_to_json(section, clients):
			return True, str(len(clients))
		return False, "write_failed"
	except Exception as e:
		return False, str(e)

