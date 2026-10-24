import tempfile
import unittest
from pathlib import Path
from code_agent.hook import PreCommitHook

class TestPreCommitHook(unittest.TestCase):
    def test_install_and_uninstall_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git" / "hooks").mkdir(parents=True)

            hook_path = PreCommitHook.install(repo_root=root)
            self.assertTrue(hook_path.is_file())
            content = hook_path.read_text(encoding="utf-8")
            self.assertIn("Running pre-commit security", content)

            uninstalled = PreCommitHook.uninstall(repo_root=root)
            self.assertTrue(uninstalled)
            self.assertFalse(hook_path.exists())

if __name__ == "__main__":
    unittest.main()
