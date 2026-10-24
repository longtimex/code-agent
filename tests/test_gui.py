import json
import unittest
from code_agent.gui_server import DESKTOP_HTML

class TestGUI(unittest.TestCase):
    def test_gui_html_content(self):
        self.assertIn("Code Analysis Agent", DESKTOP_HTML)
        self.assertIn("静态安全扫描", DESKTOP_HTML)
        self.assertIn("Agent 深度审计", DESKTOP_HTML)
        self.assertIn("技术债与重复率", DESKTOP_HTML)
        self.assertIn("自动化测试生成", DESKTOP_HTML)
        self.assertIn("Git 变更审查", DESKTOP_HTML)
        self.assertIn("模型接口设置", DESKTOP_HTML)

    def test_gui_api_endpoints_exist(self):
        self.assertIn("/api/scan", DESKTOP_HTML)
        self.assertIn("/api/agent", DESKTOP_HTML)
        self.assertIn("/api/debt", DESKTOP_HTML)
        self.assertIn("/api/testgen", DESKTOP_HTML)
        self.assertIn("/api/review", DESKTOP_HTML)
        self.assertIn("/api/config", DESKTOP_HTML)
        self.assertIn("/api/llm/test", DESKTOP_HTML)

if __name__ == "__main__":
    unittest.main()
