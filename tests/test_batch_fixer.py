import tempfile
import unittest
from pathlib import Path

from code_agent.batch_fixer import BatchFixer


class TestBatchFixer(unittest.TestCase):
    def test_fix_yaml_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "loader.py"
            target.write_text("import yaml\n\ndef load_data(text):\n    return yaml.load(text)\n", encoding="utf-8")

            results = BatchFixer.fix_file(target, backup=False)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].rule_id, "SEC-004")

            updated_content = target.read_text(encoding="utf-8")
            self.assertIn("yaml.safe_load(text)", updated_content)
            self.assertNotIn("yaml.load(text)", updated_content)

    def test_fix_verify_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "client.py"
            target.write_text("import requests\n\ndef fetch():\n    return requests.get('https://example.com', verify=False)\n", encoding="utf-8")

            results = BatchFixer.fix_file(target, backup=False)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].rule_id, "SEC-008")

            updated_content = target.read_text(encoding="utf-8")
            self.assertIn("verify=True", updated_content)

    def test_fix_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            f1 = root / "a.py"
            f2 = root / "b.py"
            f1.write_text("import yaml\nd = yaml.load('{}')\n", encoding="utf-8")
            f2.write_text("import requests\nrequests.get('url', verify=False)\n", encoding="utf-8")

            results = BatchFixer.fix_directory(root, backup=False)
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r.success for r in results))


if __name__ == "__main__":
    unittest.main()
