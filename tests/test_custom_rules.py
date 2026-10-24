import json
import tempfile
import unittest
from pathlib import Path
from code_agent.custom_rules import CustomRuleLoader

CUSTOM_CONFIG = {
    "custom_rules": [
        {
            "id": "CORP-001",
            "pattern": r"import\s+legacy_sdk",
            "title": "Deprecated Legacy SDK",
            "severity": "HIGH",
            "recommendation": "Migrate to modern_sdk v3.",
            "file_extensions": [".py"],
        }
    ]
}

class TestCustomRules(unittest.TestCase):
    def test_custom_rule_loading_and_matching(self):
        rules = CustomRuleLoader.load_from_dict(CUSTOM_CONFIG)
        self.assertEqual(len(rules), 1)

        code_bad = "import legacy_sdk\nprint('hello')\n"
        findings = CustomRuleLoader.scan_content(code_bad, "service.py", rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CORP-001")
        self.assertEqual(findings[0].severity, "HIGH")

        code_good = "import modern_sdk\nprint('hello')\n"
        findings_good = CustomRuleLoader.scan_content(code_good, "service.py", rules)
        self.assertEqual(len(findings_good), 0)

if __name__ == "__main__":
    unittest.main()
