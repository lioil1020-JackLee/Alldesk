import unittest

from app.utils.text import normalize_client_fields


class NormalizeClientFieldsTests(unittest.TestCase):
    def test_normalizes_numeric_id_and_port(self):
        out = normalize_client_fields({"tag": "A", "id": 1234.0, "pwd": " p ", "port": 5900.0})
        self.assertEqual(out["tag"], "A")
        self.assertEqual(out["id"], "1234")
        self.assertEqual(out["pwd"], "p")
        self.assertEqual(out["port"], "5900")

    def test_non_dict_input_returns_empty_fields(self):
        out = normalize_client_fields(None)
        self.assertEqual(out, {"tag": "", "id": "", "pwd": "", "port": ""})


if __name__ == "__main__":
    unittest.main()
