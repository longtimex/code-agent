"""Model Context Protocol (MCP) Standard Server.

Implements JSON-RPC 2.0 over stdio compliant with the MCP specification,
allowing Cursor, Claude Desktop, VS Code, and other AI agents to natively
invoke Code Analysis Agent tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .tools import ToolRegistry

PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """Standard Model Context Protocol (MCP) server over standard input/output."""

    def __init__(self, workspace_root: Optional[Path | str] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.registry = ToolRegistry(workspace_root=self.workspace_root)

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params", {})

        # Handle initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "code-agent-mcp",
                        "version": "0.1.0",
                    },
                },
            }

        # Notifications don't require responses
        if method in ("notifications/initialized", "initialized"):
            return None

        # Ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        # List tools
        if method == "tools/list":
            schemas = self.registry.get_schemas()
            mcp_tools = []
            for s in schemas:
                fn = s.get("function", {})
                mcp_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description"),
                    "inputSchema": fn.get("parameters", {}),
                })
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": mcp_tools},
            }

        # Call tool
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result_str = self.registry.execute(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_str}],
                },
            }

        # Method not found
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }

    def run(self) -> None:
        """Runs the main stdio event loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
