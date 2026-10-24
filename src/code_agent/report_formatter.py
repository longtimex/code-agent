"""Report formatting and terminal visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


class ReportFormatter:
    """Formats findings and agent results for Terminal, Markdown, and JSON."""

    SEVERITY_COLORS = {
        "CRITICAL": f"{BOLD}{RED}",
        "HIGH": f"{RED}",
        "MEDIUM": f"{YELLOW}",
        "LOW": f"{CYAN}",
        "INFO": f"{BLUE}",
    }

    @classmethod
    def format_terminal_findings(cls, findings: List[Finding]) -> str:
        if not findings:
            return f"\n{GREEN}✔ 未检测到明显漏洞与代码隐患。{RESET}\n"

        lines = [
            f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}",
            f"{BOLD}                 代码安全与质量扫描结果 ({len(findings)} 处发现)          {RESET}",
            f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}\n",
        ]

        # Group by severity
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        sorted_findings = sorted(
            findings,
            key=lambda f: severity_order.index(f.severity) if f.severity in severity_order else 99,
        )

        for i, f in enumerate(sorted_findings, start=1):
            color = cls.SEVERITY_COLORS.get(f.severity, "")
            lines.append(f"{BOLD}#{i} [{color}{f.severity}{RESET}{BOLD}] {f.title}{RESET} ({f.rule_id})")
            lines.append(f"   {DIM}文件:{RESET} {f.file_path}:{f.line_number}")
            if f.snippet:
                lines.append(f"   {DIM}代码:{RESET} {YELLOW}{f.snippet}{RESET}")
            lines.append(f"   {DIM}建议:{RESET} {f.recommendation}")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def format_markdown(cls, findings: List[Finding], target_name: str = "") -> str:
        lines = [
            f"# 代码分析与安全审计报告: {target_name}",
            "",
            f"**发现问题总数**: {len(findings)}",
            "",
            "| # | 严重级别 | 规则 ID | 问题描述 | 位置 |",
            "|---|---|---|---|---|",
        ]

        for i, f in enumerate(findings, start=1):
            badge = f"**{f.severity}**"
            loc = f"`{f.file_path}:{f.line_number}`"
            lines.append(f"| {i} | {badge} | `{f.rule_id}` | {f.title} | {loc} |")

        if findings:
            lines.append("\n## 详细修复建议\n")
            for i, f in enumerate(findings, start=1):
                lines.append(f"### {i}. [{f.severity}] {f.title} (`{f.rule_id}`)")
                lines.append(f"- **文件位置**: `{f.file_path}:{f.line_number}`")
                if f.snippet:
                    lines.append(f"- **相关代码**: `{f.snippet}`")
                lines.append(f"- **修复建议**: {f.recommendation}")
                lines.append("")

        return "\n".join(lines)

    @classmethod
    def export_json(cls, findings: List[Finding], output_path: str | Path) -> None:
        data = [f.to_dict() for f in findings]
        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
