"""Code Analysis Agent Orchestration Engine.

Implements the ReAct (Reasoning + Acting) loop: analyzes codebases, invokes tools,
evaluates responses, and outputs actionable technical reviews.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .llm_client import LLMMessage, OfflineHeuristicEngine, OpenAICompatibleClient
from .tools import ToolRegistry


@dataclass
class AgentStep:
    turn: int
    thought: Optional[str]
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None


@dataclass
class AgentResult:
    success: bool
    final_response: str
    steps: List[AgentStep] = field(default_factory=list)
    total_turns: int = 0


SYSTEM_PROMPT = """你是一名世界顶级软件架构师与安全审计专家。
你的任务是深入分析代码仓库、文件或代码变更（Diff），发现潜在的安全漏洞、性能瓶颈、逻辑反模式和架构缺陷，并给出具体的修复建议。

你可以调用一系列专业工具来辅助分析：
1. `get_file_outline`: 查看文件的 AST 大纲（类、函数、签名、复杂度），节省上下文空间。
2. `read_symbol`: 仅在需要深入分析某函数或类时获取具体实现。
3. `read_file_lines`: 按需阅读特定行号范围的代码。
4. `search_code`: 搜索符号引用或特定关键词。
5. `run_static_scan`: 运行确定性的 AST 与安全规则扫描器。
6. `get_git_diff`: 检视代码变更。

【工作准则】
- 保持客观严谨，优先指出高风险问题（如注入、硬编码密钥、资源泄漏、并发问题）。
- 提出具体的代码修复示例（包含修改前与修改后的代码）。
- 不要凭空捏造不存在的文件或符号，先用工具核实代码事实。
"""


class CodeAnalysisAgent:
    """Multi-turn reasoning and tool-calling agent for code analysis."""

    def __init__(
        self,
        workspace_root: Optional[Path | str] = None,
        llm_client: Optional[Any] = None,
        max_turns: int = 8,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.tool_registry = ToolRegistry(workspace_root=self.workspace_root)
        self.llm = llm_client or OfflineHeuristicEngine()
        self.max_turns = max_turns
        self.on_step = on_step

    def run(self, goal: str, target_path: Optional[str] = None) -> AgentResult:
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"目标路径: Target: {target_path or '.'}\n分析任务: {goal}",
            },
        ]

        steps: List[AgentStep] = []
        turn = 0

        while turn < self.max_turns:
            turn += 1
            tools_schema = self.tool_registry.get_schemas()

            try:
                response: LLMMessage = self.llm.chat_completion(
                    messages=messages,
                    tools=tools_schema,
                )
            except Exception as e:
                return AgentResult(
                    success=False,
                    final_response=f"Agent 执行出错: {str(e)}",
                    steps=steps,
                    total_turns=turn,
                )

            # Record thought / content
            thought = response.content

            # If no tool calls, the agent has reached a conclusion
            if not response.tool_calls:
                step = AgentStep(turn=turn, thought=thought)
                steps.append(step)
                if self.on_step:
                    self.on_step(step)

                return AgentResult(
                    success=True,
                    final_response=thought or "分析完毕，未返回具体内容。",
                    steps=steps,
                    total_turns=turn,
                )

            # Append assistant message with tool calls to context
            messages.append(response.to_dict())

            # Execute tool calls
            for tc in response.tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception:
                    args = {}

                result_str = self.tool_registry.execute(fn_name, args)

                step = AgentStep(
                    turn=turn,
                    thought=thought,
                    tool_name=fn_name,
                    tool_args=args,
                    tool_result=result_str,
                )
                steps.append(step)
                if self.on_step:
                    self.on_step(step)

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": result_str,
                })

        return AgentResult(
            success=False,
            final_response="Agent 达到最大迭代步数限制，提前结束分析。",
            steps=steps,
            total_turns=turn,
        )
