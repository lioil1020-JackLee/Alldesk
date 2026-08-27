import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.repositories import csv_repo


class CsvRepoTests(unittest.TestCase):
    def test_export_to_csv_writes_rows(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "out.csv"
            data = [
                {
                    "tag": "A",
                    "id": "1",
                    "pwd": "x",
                    "port": "5900",
                    "check_status": False,
                }
            ]
            with patch("app.repositories.csv_repo.read_clients_from_json", return_value=data):
                ok, detail = csv_repo.export_to_csv("rustdesk", str(out_path))
            self.assertTrue(ok)
            self.assertEqual(detail, "1")
            with out_path.open("r", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "1")
            self.assertEqual(rows[0]["check_status"], "false")

    def test_import_from_csv_reads_and_writes_clients(self):
        with tempfile.TemporaryDirectory() as td:
            in_path = Path(td) / "in.csv"
            in_path.write_text(
                "tag,id,pwd,port,check_status\nA,1,x,5900,false\n",
                encoding="utf-8",
            )
            with patch("app.repositories.csv_repo.write_clients_to_json", return_value=True) as m_write:
                ok, detail = csv_repo.import_from_csv("rustdesk", str(in_path))
            self.assertTrue(ok)
            self.assertEqual(detail, "1")
            self.assertTrue(m_write.called)
            written_clients = m_write.call_args.args[1]
            self.assertIs(written_clients[0]["check_status"], False)


if __name__ == "__main__":
    unittest.main()
