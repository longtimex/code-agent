import tempfile
import unittest
from pathlib import Path
from code_agent.agent import CodeAnalysisAgent
from code_agent.llm_client import OfflineHeuristicEngine

class TestAgent(unittest.TestCase):
    def test_agent_run_offline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "vuln.py"
            p.write_text('import os\n\ndef run(cmd):\n    eval(cmd)\n    os.system(cmd)\n', encoding="utf-8")

            agent = CodeAnalysisAgent(
                workspace_root=tmpdir,
                llm_client=OfflineHeuristicEngine(),
                max_turns=5,
            )

            result = agent.run(goal="审计代码安全漏洞", target_path="vuln.py")
            self.assertTrue(result.success)
            self.assertGreater(result.total_turns, 0)
            self.assertIn("代码分析与安全审计报告", result.final_response)
            self.assertIn("SEC-001", result.final_response)

if __name__ == "__main__":
    unittest.main()
