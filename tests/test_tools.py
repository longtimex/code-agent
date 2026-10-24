import json
import tempfile
import unittest
from pathlib import Path
from code_agent.tools import ToolRegistry

class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.registry = ToolRegistry(workspace_root=self.workspace)

        # Create a sample file
        self.sample_file = self.workspace / "sample.py"
        self.sample_file.write_text(
            'def hello(name: str):\n    """Say hello"""\n    print("Hello " + name)\n',
            encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schemas(self):
        schemas = self.registry.get_schemas()
        tool_names = [s["function"]["name"] for s in schemas]
        self.assertIn("get_file_outline", tool_names)
        self.assertIn("read_symbol", tool_names)
        self.assertIn("read_file_lines", tool_names)
        self.assertIn("search_code", tool_names)
        self.assertIn("run_static_scan", tool_names)

    def test_get_file_outline(self):
        res = self.registry.execute("get_file_outline", {"file_path": "sample.py"})
        data = json.loads(res)
        self.assertIn("skeleton", data)
        self.assertEqual(data["symbols_count"], 1)

    def test_read_symbol(self):
        res = self.registry.execute("read_symbol", {"file_path": "sample.py", "symbol_name": "hello"})
        data = json.loads(res)
        self.assertIn("def hello", data["code"])

    def test_read_file_lines(self):
        res = self.registry.execute("read_file_lines", {"file_path": "sample.py", "start_line": 1, "end_line": 2})
        data = json.loads(res)
        self.assertIn("def hello", data["content"])

if __name__ == "__main__":
    unittest.main()

    def test_new_tools_execution(self):
        # 1. check_performance
        perf_res = json.loads(self.registry.execute("check_performance", {"target_path": "sample.py"}))
        self.assertIn("findings_count", perf_res)

        # 2. generate_documentation
        doc_res = json.loads(self.registry.execute("generate_documentation", {"target_path": "sample.py", "doc_type": "api"}))
        self.assertIn("api_doc", doc_res)

        # 3. audit_licenses
        lic_res = json.loads(self.registry.execute("audit_licenses", {"target_path": "."}))
        self.assertIn("detected_licenses", lic_res)

        # 4. batch_fix_code
        fix_target = self.workspace / "vulnerable.py"
        fix_target.write_text("import yaml\nyaml.load('abc')\n", encoding="utf-8")
        fix_res = json.loads(self.registry.execute("batch_fix_code", {"target_path": "vulnerable.py", "backup": False}))
        self.assertEqual(fix_res["fixed_count"], 1)
