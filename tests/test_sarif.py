import tempfile
import unittest
from pathlib import Path
from code_agent.models import Finding
from code_agent.sarif import SARIFExporter

class TestSARIFExporter(unittest.TestCase):
    def test_sarif_export(self):
        findings = [
            Finding(
                rule_id="SEC-001",
                title="Dynamic Execution",
                severity="CRITICAL",
                file_path="src/main.py",
                line_number=12,
                snippet="eval(code)",
                recommendation="Do not use eval()",
            ),
            Finding(
                rule_id="CODE-001",
                title="Bare Except",
                severity="MEDIUM",
                file_path="src/utils.py",
                line_number=45,
                snippet="except:",
                recommendation="Catch specific exception",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "results.sarif"
            SARIFExporter.export(findings, out_file)
            self.assertTrue(out_file.is_file())

            sarif_data = SARIFExporter.to_sarif_dict(findings)
            self.assertEqual(sarif_data["version"], "2.1.0")
            runs = sarif_data["runs"]
            self.assertEqual(len(runs), 1)
            results = runs[0]["results"]
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["level"], "error")
            self.assertEqual(results[1]["level"], "warning")

if __name__ == "__main__":
    unittest.main()
