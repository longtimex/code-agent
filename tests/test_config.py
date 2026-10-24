import tempfile
import unittest
from pathlib import Path
from code_agent.config import AgentConfig

class TestConfig(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AgentConfig(
                max_complexity_threshold=15,
                disabled_rules=["SEC-005"],
                severity_overrides={"SEC-001": "HIGH"},
                openai_base_url="https://api.deepseek.com/v1",
                openai_api_key="sk-test-key-12345",
                default_model="deepseek-chat",
            )
            saved_path = cfg.save(root_dir=tmpdir)
            self.assertTrue(saved_path.is_file())

            loaded = AgentConfig.load(root_dir=tmpdir)
            self.assertEqual(loaded.max_complexity_threshold, 15)
            self.assertEqual(loaded.disabled_rules, ["SEC-005"])
            self.assertEqual(loaded.severity_overrides.get("SEC-001"), "HIGH")
            self.assertEqual(loaded.openai_base_url, "https://api.deepseek.com/v1")
            self.assertEqual(loaded.openai_api_key, "sk-test-key-12345")
            self.assertEqual(loaded.default_model, "deepseek-chat")

if __name__ == "__main__":
    unittest.main()
