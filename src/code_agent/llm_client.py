"""LLM Client Layer.

Supports standard OpenAI-compatible HTTP endpoints (via standard library urllib)
and an intelligent offline fallback engine for zero-dependency local testing.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import AgentConfig


@dataclass
class ToolCallFunction:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: ToolCallFunction = field(default_factory=lambda: ToolCallFunction("", "{}"))


@dataclass
class LLMMessage:
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        return data


class OpenAICompatibleClient:
    """Zero-dependency HTTP client for OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        config: Optional[AgentConfig] = None,
    ) -> None:
        cfg = config or AgentConfig.load()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or cfg.openai_api_key or ""
        raw_base = (
            base_url
            or os.environ.get("OPENAI_BASE_URL")
            or cfg.openai_base_url
            or "https://api.openai.com/v1"
        )
        self.base_url = raw_base.rstrip("/")
        self.model = model or cfg.default_model or "gpt-4o"
        self.timeout = timeout

    def ping(self) -> Dict[str, Any]:
        """Tests connectivity to the LLM endpoint with a minimal query."""
        try:
            msg = self.chat_completion(
                messages=[{"role": "user", "content": "ping"}],
                temperature=0.0,
            )
            return {"success": True, "model": self.model, "response": (msg.content or "").strip()[:100]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
    ) -> LLMMessage:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choice = body["choices"][0]["message"]
                tool_calls = None
                if "tool_calls" in choice and choice["tool_calls"]:
                    tool_calls = []
                    for tc in choice["tool_calls"]:
                        fn = ToolCallFunction(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        )
                        tool_calls.append(ToolCall(id=tc["id"], function=fn))
                return LLMMessage(
                    role=choice.get("role", "assistant"),
                    content=choice.get("content"),
                    tool_calls=tool_calls,
                )
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API Error ({e.code}): {err_msg}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with LLM endpoint: {e}") from e


class OfflineHeuristicEngine:
    """Deterministic reasoning engine simulating Agent tool calling and analysis.

    Enables testing and running code analysis without requiring external API keys.
    """

    def __init__(self, model: str = "offline-heuristic") -> None:
        self.model = model
        self.step = 0

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.0,
    ) -> LLMMessage:
        self.step += 1
        last_msg = messages[-1]

        # Step 1: In the first turn, trigger static scan and outline tools
        if self.step == 1:
            # Extract target path from the user's initial prompt
            target_path = "."
            user_content = messages[1].get("content", "") if len(messages) > 1 else ""
            if "Target:" in user_content:
                target_path = user_content.split("Target:")[1].split("\n")[0].strip()

            tool_calls = [
                ToolCall(
                    id="call_static_scan_1",
                    function=ToolCallFunction(
                        name="run_static_scan",
                        arguments=json.dumps({"target_path": target_path}),
                    ),
                ),
            ]
            return LLMMessage(
                role="assistant",
                content="我将首先调用代码静态规则扫描引擎，检查目标路径中的安全隐患、反模式和复杂度风险。",
                tool_calls=tool_calls,
            )

        # Step 2: In the second turn, synthesize the tool results into a structured audit report
        # Collect all tool results from message history
        tool_outputs = []
        for msg in messages:
            if msg.get("role") == "tool":
                tool_outputs.append(msg.get("content", ""))

        analysis_summary = "### 代码分析与安全审计报告\n\n"
        findings_count = 0
        details = []

        for out_str in tool_outputs:
            try:
                data = json.loads(out_str)
                if isinstance(data, dict) and "findings" in data:
                    for f in data["findings"]:
                        findings_count += 1
                        details.append(
                            f"- **[{f['severity']}] {f['title']}** (`{f.get('rule_id', 'UNKNOWN')}`)\n"
                            f"  - **位置**: `{f['file_path']}:{f['line_number']}`\n"
                            f"  - **代码片段**: `{f['snippet']}`\n"
                            f"  - **修复建议**: {f['recommendation']}\n"
                        )
            except Exception:
                pass

        if findings_count == 0:
            analysis_summary += "✅ **扫描完成**：未发现高危安全漏洞或明显反模式，代码基本结构良好。\n"
        else:
            analysis_summary += f"⚠️ **共检测到 {findings_count} 个潜在问题与安全隐患**：\n\n"
            analysis_summary += "\n".join(details)
            analysis_summary += "\n#### 修复与重构建议：\n1. 优先修复 CRITICAL 及 HIGH 级别隐患（如硬编码密钥、动态执行及注入风险）。\n2. 对复杂度较高的函数进行模块化拆解。\n"

        return LLMMessage(
            role="assistant",
            content=analysis_summary,
            tool_calls=None,
        )
