import tempfile
import unittest
from pathlib import Path
from code_agent.patcher import Patcher

class TestPatcher(unittest.TestCase):
    def test_apply_replacement_with_syntax_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "app.py"
            target.write_text('def run():\n    return 42\n', encoding="utf-8")

            # 1. Successful replacement
            res = Patcher.apply_replacement(target, "return 42", "return 100", backup=True)
            self.assertTrue(res["success"])
            self.assertIn("return 100", target.read_text(encoding="utf-8"))
            self.assertTrue(Path(tmpdir, "app.py.bak").is_file())

            # 2. Syntax validation rejection (e.g. invalid syntax)
            res_bad = Patcher.apply_replacement(target, "return 100", "return def invalid !!!", backup=False)
            self.assertFalse(res_bad["success"])
            self.assertIn("Syntax validation failed", res_bad["error"])
            # Ensure file was not corrupted
            self.assertIn("return 100", target.read_text(encoding="utf-8"))

            # 3. Revert backup
            reverted = Patcher.revert_backup(target)
            self.assertTrue(reverted)
            self.assertIn("return 42", target.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
