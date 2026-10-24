import tempfile
import unittest
from pathlib import Path

from code_agent.doc_generator import DocGenerator


class TestDocGenerator(unittest.TestCase):
    def test_generate_api_doc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "math_utils.py"
            target.write_text(
                '"""Utility math helpers."""\n\n'
                "class Calculator:\n"
                '    """Basic arithmetic calculator."""\n'
                "    def add(self, a: int, b: int) -> int:\n"
                '        """Sum two numbers."""\n'
                "        return a + b\n\n"
                "def multiply(x: int, y: int) -> int:\n"
                '    """Multiply numbers."""\n'
                "    return x * y\n",
                encoding="utf-8",
            )

            doc = DocGenerator.generate_api_doc(target)
            self.assertIn("# API 接口参考文档", doc)
            self.assertIn("class Calculator", doc)
            self.assertIn("Basic arithmetic calculator", doc)
            self.assertIn("multiply", doc)

    def test_generate_architecture_doc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mod_a = root / "module_a.py"
            mod_b = root / "module_b.py"

            mod_a.write_text("from module_b import helper\n\ndef run():\n    helper()\n", encoding="utf-8")
            mod_b.write_text("def helper():\n    return 42\n", encoding="utf-8")

            doc = DocGenerator.generate_architecture_doc(root)
            self.assertIn("项目架构与模块拓扑指南", doc)
            self.assertIn("模块依赖拓扑图", doc)
            self.assertIn("module_a", doc)
            self.assertIn("module_b", doc)


if __name__ == "__main__":
    unittest.main()
