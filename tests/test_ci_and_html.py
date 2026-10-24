import tempfile
import unittest
from pathlib import Path
from code_agent.ci_integration import CIIntegration
from code_agent.html_report import HTMLReportGenerator
from code_agent.models import Finding

class TestCIAndHTML(unittest.TestCase):
    def test_html_report_generation(self):
        findings = [
            Finding(
                rule_id="SEC-001",
                title="Dynamic Execution",
                severity="CRITICAL",
                file_path="app.py",
                line_number=10,
                snippet="eval(x)",
                recommendation="Do not use eval",
            )
        ]
        html = HTMLReportGenerator.generate(findings, target_name="DemoApp")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("CRITICAL", html)
        self.assertIn("eval(x)", html)
        self.assertIn("DemoApp", html)

    def test_ci_workflow_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wf_file = CIIntegration.generate_workflow_file(tmpdir)
            self.assertTrue(wf_file.is_file())
            content = wf_file.read_text(encoding="utf-8")
            self.assertIn("Code Agent Review", content)

if __name__ == "__main__":
    unittest.main()
