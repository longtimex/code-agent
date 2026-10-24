import tempfile
import unittest
from pathlib import Path

from code_agent.perf_advisor import PerformanceAdvisor


class TestPerformanceAdvisor(unittest.TestCase):
    def test_detect_regex_in_loop(self):
        code = """
import re

def process_items(items):
    for item in items:
        m = re.search(r"\\d+", item)
        if m:
            print(m.group(0))
"""
        findings = PerformanceAdvisor.scan_content(code, file_path="sample.py")
        rule_ids = [f.rule_id for f in findings]
        self.assertIn("PERF-101", rule_ids)
        finding = next(f for f in findings if f.rule_id == "PERF-101")
        self.assertIn("Regex Compilation Inside Loop", finding.title)

    def test_detect_string_concat_in_loop(self):
        code = """
def build_string(lines):
    result = ""
    for line in lines:
        result += line
    return result
"""
        findings = PerformanceAdvisor.scan_content(code, file_path="concat.py")
        rule_ids = [f.rule_id for f in findings]
        self.assertIn("PERF-102", rule_ids)
        finding = next(f for f in findings if f.rule_id == "PERF-102")
        self.assertIn("Repeated String Concatenation", finding.title)

    def test_detect_open_in_loop(self):
        code = """
def read_all(paths):
    for path in paths:
        f = open(path, "r")
        content = f.read()
        f.close()
"""
        findings = PerformanceAdvisor.scan_content(code, file_path="io_loop.py")
        rule_ids = [f.rule_id for f in findings]
        self.assertIn("PERF-104", rule_ids)

    def test_detect_pandas_iterrows(self):
        code = """
def iterate_rows(df):
    for idx, row in df.iterrows():
        print(row["val"])
"""
        findings = PerformanceAdvisor.scan_content(code, file_path="pandas_loop.py")
        rule_ids = [f.rule_id for f in findings]
        self.assertIn("PERF-105", rule_ids)

    def test_scan_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            f1 = root / "script.py"
            f1.write_text(
                "import re\nfor x in [1, 2]:\n    re.compile(r'abc')\n",
                encoding="utf-8",
            )
            findings = PerformanceAdvisor.scan_directory(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].rule_id, "PERF-101")


if __name__ == "__main__":
    unittest.main()
