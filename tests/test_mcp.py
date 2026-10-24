import json
import unittest
from code_agent.mcp_server import MCPServer

class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()

    def test_mcp_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = self.server.handle_request(req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        self.assertIn("capabilities", resp["result"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "code-agent-mcp")

    def test_mcp_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        resp = self.server.handle_request(req)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("get_file_outline", tool_names)
        self.assertIn("run_static_scan", tool_names)
        self.assertIn("find_symbol_callers", tool_names)

    def test_mcp_ping(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
        resp = self.server.handle_request(req)
        self.assertEqual(resp["result"], {})

if __name__ == "__main__":
    unittest.main()
