"""Native Tkinter Desktop Window Module.

Provides a pure Win32 native desktop window using Python's standard Tkinter,
suitable for compiling directly into a standalone Windows .exe with PyInstaller.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .debt_estimator import DebtEstimator
from .git_tools import GitTools
from .pr_reviewer import PRReviewer
from .security_rules import CodeRuleEngine
from .test_generator import TestGenerator
from .agent import CodeAnalysisAgent
from .config import AgentConfig
from .llm_client import OfflineHeuristicEngine, OpenAICompatibleClient


class TkinterDesktopApp:
    """Native Tkinter desktop window application."""

    def __init__(self) -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox, ttk
            self.tk = tk
            self.ttk = ttk
            self.filedialog = filedialog
            self.messagebox = messagebox
        except ImportError:
            raise RuntimeError(
                "Tkinter is not available in the current Python environment.\n"
                "Please run `code-agent gui` instead, or install Python with Tk support on Windows."
            )

        self.root = self.tk.Tk()
        self.root.title("Code Analysis Agent - 桌面安全分析工具")
        self.root.geometry("860x620")
        self.root.minsize(700, 500)
        self._build_ui()

    def _build_ui(self) -> None:
        # Top Frame: Path selection
        top_frame = self.ttk.LabelFrame(self.root, text=" 目标配置 ", padding=10)
        top_frame.pack(fill="x", padx=12, pady=8)

        self.ttk.Label(top_frame, text="目标路径:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.path_entry = self.ttk.Entry(top_frame, width=50)
        self.path_entry.insert(0, str(Path.cwd()))
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        browse_btn = self.ttk.Button(top_frame, text="浏览文件夹...", command=self._browse_folder)
        browse_btn.grid(row=0, column=2, padx=4, pady=4)

        # Action Selector
        self.ttk.Label(top_frame, text="分析功能:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.action_var = self.tk.StringVar(value="scan")
        actions_combo = self.ttk.Combobox(
            top_frame,
            textvariable=self.action_var,
            values=[
                ("scan", "静态安全与质量扫描 (Scan)"),
                ("agent", "AI Agent 多轮深度推理审计 (Agent)"),
                ("debt", "技术债与代码可维护性评估 (Debt)"),
                ("review", "Git 变更审查 (Review)"),
                ("testgen", "自动化单元测试生成 (Testgen)"),
            ],
            state="readonly",
        )
        actions_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        btn_box = self.ttk.Frame(top_frame)
        btn_box.grid(row=1, column=2, padx=4, pady=4)

        run_btn = self.ttk.Button(btn_box, text="▶ 开始分析", command=self._run_action)
        run_btn.pack(side="left", padx=2)

        settings_btn = self.ttk.Button(btn_box, text="⚙️ LLM 设置...", command=self._open_settings)
        settings_btn.pack(side="left", padx=2)

        top_frame.columnconfigure(1, weight=1)

        # Middle: Output Area
        output_frame = self.ttk.LabelFrame(self.root, text=" 分析结果 ", padding=10)
        output_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.text_output = self.tk.Text(
            output_frame,
            wrap="word",
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 10),
        )
        self.text_output.pack(side="left", fill="both", expand=True)

        scrollbar = self.ttk.Scrollbar(output_frame, orient="vertical", command=self.text_output.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_output.config(yscrollcommand=scrollbar.set)

    def _open_settings(self) -> None:
        cfg = AgentConfig.load()
        win = self.tk.Toplevel(self.root)
        win.title("大模型接口与密钥配置")
        win.geometry("520x300")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        frame = self.ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)

        self.ttk.Label(frame, text="Base URL (端点地址):").pack(anchor="w", pady=(0, 2))
        url_entry = self.ttk.Entry(frame, width=50)
        url_entry.insert(0, cfg.openai_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        url_entry.pack(fill="x", pady=(0, 10))

        self.ttk.Label(frame, text="API Key (密钥令牌):").pack(anchor="w", pady=(0, 2))
        key_entry = self.ttk.Entry(frame, width=50, show="*")
        key_entry.insert(0, cfg.openai_api_key or os.environ.get("OPENAI_API_KEY", ""))
        key_entry.pack(fill="x", pady=(0, 10))

        self.ttk.Label(frame, text="Model Name (模型名称):").pack(anchor="w", pady=(0, 2))
        model_entry = self.ttk.Entry(frame, width=50)
        model_entry.insert(0, cfg.default_model or "gpt-4o")
        model_entry.pack(fill="x", pady=(0, 16))

        def save_and_close() -> None:
            cfg.openai_base_url = url_entry.get().strip()
            cfg.openai_api_key = key_entry.get().strip()
            cfg.default_model = model_entry.get().strip() or "gpt-4o"
            cfg.save()
            os.environ["OPENAI_BASE_URL"] = cfg.openai_base_url
            os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
            self.messagebox.showinfo("成功", "LLM 接口配置已成功保存至 .code-agent.json 并生效！")
            win.destroy()

        save_btn = self.ttk.Button(frame, text="💾 保存并应用", command=save_and_close)
        save_btn.pack(anchor="e")

    def _browse_folder(self) -> None:
        folder = self.filedialog.askdirectory(initialdir=self.path_entry.get())
        if folder:
            self.path_entry.delete(0, self.tk.END)
            self.path_entry.insert(0, folder)

    def _run_action(self) -> None:
        target_path = Path(self.path_entry.get().strip())
        action = self._selected_action()
        self._set_output("⏳ 正在分析中，请稍候...\n\n")

        try:
            result_text = self._dispatch_action(action, target_path)
        except Exception as e:
            result_text = f"❌ 执行出错: {str(e)}\n"

        self._set_output(result_text)

    def _selected_action(self) -> str:
        # Combobox entries may render as "value label", so keep the first token.
        action_val = self.action_var.get()
        return action_val.split()[0] if " " in action_val else action_val

    def _set_output(self, text: str) -> None:
        self.text_output.delete("1.0", self.tk.END)
        self.text_output.insert(self.tk.END, text)
        self.root.update()

    def _dispatch_action(self, action: str, target_path: Path) -> str:
        if "agent" in action:
            return self._run_agent(target_path)
        if "scan" in action:
            return self._run_scan(target_path)
        if "debt" in action:
            return self._run_debt(target_path)
        if "testgen" in action:
            return TestGenerator.generate_test_file(target_path, output_framework="pytest")
        if "review" in action:
            return PRReviewer.generate_review_comment(repo_root=target_path)
        return "未知操作类型。"

    def _run_agent(self, target_path: Path) -> str:
        cfg = AgentConfig.load()
        api_key = cfg.openai_api_key or os.environ.get("OPENAI_API_KEY")
        base_url = cfg.openai_base_url or os.environ.get("OPENAI_BASE_URL")
        model = cfg.default_model or "gpt-4o"

        if api_key:
            llm = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
        else:
            llm = OfflineHeuristicEngine(model=model)

        agent = CodeAnalysisAgent(llm_client=llm)
        res = agent.run(goal="全面审查代码安全漏洞、异常处理与性能缺陷", target_path=str(target_path))
        return res.final_response

    def _run_scan(self, target_path: Path) -> str:
        if target_path.is_dir():
            findings = CodeRuleEngine.scan_directory(target_path)
        else:
            findings = CodeRuleEngine.scan_file(target_path)

        out = [
            "=== 静态安全与质量扫描结果 ===",
            f"目标: {target_path}",
            f"发现隐患总数: {len(findings)}\n",
        ]
        for i, f in enumerate(findings, start=1):
            out.append(f"#{i} [{f.severity}] {f.title} ({f.rule_id})")
            out.append(f"   位置: {f.file_path}:{f.line_number}")
            if f.snippet:
                out.append(f"   代码: {f.snippet}")
            out.append(f"   建议: {f.recommendation}\n")
        return "\n".join(out)

    @staticmethod
    def _run_debt(target_path: Path) -> str:
        report = DebtEstimator.analyze(target_path)
        return (
            f"=== 代码可维护性指数与技术债评估 ===\n"
            f"可维护性评级 (MI): Grade {report.maintainability_grade} ({report.maintainability_index:.1f}/100)\n"
            f"分析行数 (LOC): {report.total_loc:,} 行 ({report.total_files} 个文件)\n"
            f"预估修复工时: {report.total_debt_hours:.1f} 小时 (共 {report.total_findings} 处发现)\n"
            f"重复代码块: {report.duplicates_count} 处\n"
        )

    def run(self) -> None:
        self.root.mainloop()


def launch_tk() -> None:
    app = TkinterDesktopApp()
    app.run()
