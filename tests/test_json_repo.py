import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.repositories import json_repo


class JsonRepoTests(unittest.TestCase):
    def test_dump_json_server_first_keeps_server_config_first(self):
        payload = {"rustdesk": [], "server_config": {"server": "s"}, "anydesk": []}
        dumped = json_repo.dump_json_server_first(payload)
        self.assertTrue(dumped.strip().startswith('{\n  "server_config"'))

    def test_load_and_save_server_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "Alldesk.json"
            db_path.write_text(json.dumps({"rustdesk": [], "anydesk": [], "tightvnc": []}), encoding="utf-8")

            with patch("app.repositories.json_repo.get_app_path", return_value=str(db_path)):
                cfg = {
                    "server": "example.local",
                    "key": "abc",
                    "rustdesk_api_port": 21114,
                    "api_username": "u",
                    "api_password": "p",
                }
                ok = json_repo.save_server_config(cfg)
                self.assertTrue(ok)

                loaded = json_repo.load_server_config()
                self.assertEqual(loaded["server"], "example.local")
                self.assertEqual(loaded["key"], "abc")
                self.assertEqual(loaded["rustdesk_api_port"], 21114)


if __name__ == "__main__":
    unittest.main()
