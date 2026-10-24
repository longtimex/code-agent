"""Interactive Terminal Chat / REPL Module.

Provides an interactive console session to converse with the Code Analysis Agent,
inspect codebase structure, query symbols, and trigger audit commands dynamically.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .agent import AgentStep, CodeAnalysisAgent
from .ast_parser import ASTParser
from .call_graph import DependencyGraph
from .config import AgentConfig
from .git_tools import GitTools
from .llm_client import OfflineHeuristicEngine, OpenAICompatibleClient
from .report_formatter import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW, ReportFormatter
from .security_rules import CodeRuleEngine


def print_step(step: AgentStep) -> None:
    if step.thought:
        print(f"{CYAN}🤔 Agent 思考:{RESET} {step.thought.strip()}")
    if step.tool_name:
        print(f"{YELLOW}🔧 工具调用:{RESET} `{step.tool_name}` ({step.tool_args})")


class InteractiveREPL:
    """Terminal REPL interface for the Code Analysis Agent."""

    def __init__(
        self,
        workspace_root: Optional[Path | str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.workspace = Path(workspace_root) if workspace_root else (GitTools.get_repo_root() or Path.cwd())
        self.cfg = AgentConfig.load(self.workspace)

        key = api_key or os.environ.get("OPENAI_API_KEY") or self.cfg.openai_api_key
        url = base_url or os.environ.get("OPENAI_BASE_URL") or self.cfg.openai_base_url

        if key:
            self.llm = OpenAICompatibleClient(api_key=key, base_url=url, model=model)
            self.mode_label = f"在线 API ({model} @ {self.llm.base_url})"
        else:
            self.llm = OfflineHeuristicEngine(model=model)
            self.mode_label = "本地离线启发式引擎"

        self.agent = CodeAnalysisAgent(
            workspace_root=self.workspace,
            llm_client=self.llm,
            on_step=print_step,
        )

    def print_banner(self) -> None:
        print(f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
        print(f"{BOLD}          🤖 Code Analysis Agent - Interactive Terminal Console  {RESET}")
        print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
        print(f" 工作区: {CYAN}{self.workspace}{RESET}")
        print(f" 运行模式: {GREEN}{self.mode_label}{RESET}")
        print(f" 输入任何自然语言问题由 Agent 自主分析，或输入 {YELLOW}/help{RESET} 查看内置快捷指令。")
        print(f" 输入 {YELLOW}/exit{RESET} 或按 Ctrl+C 退出。\n")

    def print_help(self) -> None:
        print(f"\n{BOLD}内置快捷指令:{RESET}")
        print(f"  {YELLOW}/scan [path]{RESET}        快速对指定路径执行静态安全审计 (默认当前目录)")
        print(f"  {YELLOW}/outline <file>{RESET}     提取指定 Python 文件的 AST 骨架与类/函数签名")
        print(f"  {YELLOW}/diff [ref]{RESET}         检视当前工作区或指定 Git Ref 的变更")
        print(f"  {YELLOW}/callers <symbol>{RESET}   查找特定符号在整个项目中的跨文件调用点")
        print(f"  {YELLOW}/blast <file>{RESET}       计算指定文件被修改后的影响传播半径")
        print(f"  {YELLOW}/config{RESET}             查看当前大模型配置 (Base URL, 模型, API Key)")
        print(f"  {YELLOW}/set url <url>{RESET}      运行时动态切换 Base URL")
        print(f"  {YELLOW}/set key <key>{RESET}      运行时动态设置 API Key 并切换为在线模式")
        print(f"  {YELLOW}/set model <name>{RESET}   运行时动态切换模型名称")
        print(f"  {YELLOW}/clear{RESET}              清屏")
        print(f"  {YELLOW}/exit{RESET}               退出交互终端\n")

    COMMANDS = {
        "/exit": "_cmd_exit",
        "/quit": "_cmd_exit",
        ":q": "_cmd_exit",
        "/help": "_cmd_help",
        "/?": "_cmd_help",
        "/clear": "_cmd_clear",
        "/scan": "_cmd_scan",
        "/outline": "_cmd_outline",
        "/diff": "_cmd_diff",
        "/callers": "_cmd_callers",
        "/blast": "_cmd_blast",
        "/config": "_cmd_config",
        "/set": "_cmd_set",
    }

    def handle_command(self, cmd_line: str) -> bool:
        parts = cmd_line.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handler_name = self.COMMANDS.get(command)
        if handler_name is None:
            print(f"{RED}未知指令: {command}。输入 /help 查看帮助。{RESET}")
            return True
        return getattr(self, handler_name)(arg)

    def _cmd_exit(self, arg: str) -> bool:
        print(f"\n{GREEN}感谢使用 Code Analysis Agent，再见！{RESET}")
        return False

    def _cmd_help(self, arg: str) -> bool:
        self.print_help()
        return True

    def _cmd_clear(self, arg: str) -> bool:
        print("\033[2J\033[H", end="")
        self.print_banner()
        return True

    def _cmd_scan(self, arg: str) -> bool:
        target = Path(arg) if arg else self.workspace
        findings = CodeRuleEngine.scan_directory(target) if target.is_dir() else CodeRuleEngine.scan_file(target)
        print(ReportFormatter.format_terminal_findings(findings))
        return True

    def _cmd_outline(self, arg: str) -> bool:
        if not arg:
            print(f"{RED}用法: /outline <file_path>{RESET}")
            return True
        target = self.workspace / arg if not Path(arg).is_absolute() else Path(arg)
        if not target.is_file():
            print(f"{RED}错误: 文件 '{target}' 不存在{RESET}")
            return True
        skeleton = ASTParser.get_skeleton(target.read_text(encoding="utf-8", errors="replace"))
        print(f"\n{BOLD}📄 AST 骨架: {target.name}{RESET}\n{skeleton}\n")
        return True

    def _cmd_diff(self, arg: str) -> bool:
        ref = arg or "HEAD"
        diff = GitTools.get_diff(repo_path=self.workspace, ref=ref)
        if not diff:
            print(f"{GREEN}✔ 没有检测到 Git 代码变更。{RESET}")
        else:
            print(f"\n{BOLD}Git 变更差异 ({ref}):{RESET}\n{diff[:3000]}\n")
        return True

    def _cmd_callers(self, arg: str) -> bool:
        if not arg:
            print(f"{RED}用法: /callers <symbol_name>{RESET}")
            return True
        callers = DependencyGraph(root_dir=self.workspace).find_callers(arg)
        print(f"\n{BOLD}🔎 '{arg}' 的调用点 ({len(callers)}):{RESET}")
        for c in callers:
            print(f"  - {c.caller_file}:{c.line_number} (函数: `{c.caller_function}`)")
        print()
        return True

    def _cmd_blast(self, arg: str) -> bool:
        if not arg:
            print(f"{RED}用法: /blast <file_path>{RESET}")
            return True
        affected = DependencyGraph(root_dir=self.workspace).get_blast_radius(arg)
        print(f"\n{BOLD}💥 '{arg}' 的影响半径 ({len(affected)} 个关联文件):{RESET}")
        for f in affected:
            print(f"  - {f}")
        print()
        return True

    def _cmd_config(self, arg: str) -> bool:
        print(f"\n{BOLD}当前 LLM 接口配置:{RESET}")
        if isinstance(self.llm, OpenAICompatibleClient):
            print(f"  Base URL: {CYAN}{self.llm.base_url}{RESET}")
            print(f"  Model:    {GREEN}{self.llm.model}{RESET}")
            print(f"  API Key:  {self._masked_key()}")
        else:
            print(f"  模式: {YELLOW}本地离线启发式引擎 (未配置 API Key){RESET}")
            print(f"  提示: 可使用 `/set key <你的APIKey>` 或 `/set url <BaseURL>` 立即切换到在线大模型")
        print()
        return True

    def _masked_key(self) -> str:
        key = self.llm.api_key
        return f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "****"

    def _cmd_set(self, arg: str) -> bool:
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print(f"{RED}用法: /set [url|key|model] <value>{RESET}")
            return True

        subcmd, value = parts[0].lower(), parts[1].strip()
        handler = {"url": self._set_url, "key": self._set_key, "model": self._set_model}.get(subcmd)
        if handler is None:
            print(f"{RED}未知配置项: {subcmd} (可选: url, key, model){RESET}")
            return True
        handler(value)
        return True

    def _set_url(self, value: str) -> None:
        if not isinstance(self.llm, OpenAICompatibleClient):
            self.llm = OpenAICompatibleClient(base_url=value)
            self.agent.llm = self.llm
        else:
            self.llm.base_url = value.rstrip("/")
        print(f"{GREEN}✔ Base URL 已设置为: {self.llm.base_url}{RESET}")

    def _set_key(self, value: str) -> None:
        if not isinstance(self.llm, OpenAICompatibleClient):
            self.llm = OpenAICompatibleClient(api_key=value)
            self.agent.llm = self.llm
        else:
            self.llm.api_key = value
        print(f"{GREEN}✔ API Key 已设置，当前已切换为在线 API 模式{RESET}")

    def _set_model(self, value: str) -> None:
        self.llm.model = value
        print(f"{GREEN}✔ 运行模型已设置为: {value}{RESET}")

    def run(self) -> None:
        self.print_banner()

        while True:
            try:
                user_input = input(f"{BOLD}{CYAN}code-agent > {RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{GREEN}已退出交互终端。{RESET}")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                keep_running = self.handle_command(user_input)
                if not keep_running:
                    break
                continue

            # Free-form natural language query handled by the Agent
            print()
            result = self.agent.run(goal=user_input, target_path=".")
            print(f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
            print(f"{BOLD}                      Agent 回复                                 {RESET}")
            print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}\n")
            print(result.final_response)
            print()
