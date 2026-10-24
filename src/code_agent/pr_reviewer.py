"""Automated Pull Request (PR) Review Generator.

Produces comprehensive, GitHub-ready PR review comments with blast radius warnings,
severity breakdown, and code suggestions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .call_graph import DependencyGraph
from .config import AgentConfig
from .git_tools import GitTools
from .models import Finding
from .security_rules import CodeRuleEngine


class PRReviewer:
    """Performs deep PR review on changed files with blast radius impact analysis."""

    @classmethod
    def generate_review_comment(
        cls,
        repo_root: Optional[Path | str] = None,
        ref: str = "HEAD",
    ) -> str:
        root = GitTools.get_repo_root(repo_root) or Path.cwd()
        changed_files = GitTools.get_changed_files(repo_path=root, ref=ref)

        if not changed_files:
            return "## 🤖 Code Agent PR Review\n\n✅ 没有检测到任何待审查的代码变更。"

        diff_text = GitTools.get_diff(repo_path=root, ref=ref)
        file_diffs = GitTools.parse_unified_diff(diff_text)
        graph = DependencyGraph(root_dir=root)
        config = AgentConfig.load(root)

        all_findings: List[Finding] = []
        blast_radii: Dict[str, List[str]] = {}

        for fd in file_diffs:
            target_p = root / fd.new_path
            if target_p.is_file():
                findings = CodeRuleEngine.scan_file(target_p, config=config)
                changed_lines = set(fd.changed_line_numbers)
                if changed_lines:
                    relevant = [f for f in findings if f.line_number in changed_lines]
                    all_findings.extend(relevant)
                else:
                    all_findings.extend(findings)

                # Compute blast radius
                affected = graph.get_blast_radius(fd.new_path)
                if affected:
                    blast_radii[fd.new_path] = affected

        crit = sum(1 for f in all_findings if f.severity == "CRITICAL")
        high = sum(1 for f in all_findings if f.severity == "HIGH")
        med = sum(1 for f in all_findings if f.severity == "MEDIUM")
        low = sum(1 for f in all_findings if f.severity in ("LOW", "INFO"))

        # Determine decision
        if crit > 0:
            status_badge = "❌ **CHANGES REQUESTED** (发现致命阻断隐患)"
        elif high > 0:
            status_badge = "⚠️ **NEEDS ATTENTION** (存在高风险安全缺陷)"
        elif all_findings:
            status_badge = "🟡 **APPROVED WITH SUGGESTIONS** (建议优化反模式)"
        else:
            status_badge = "✅ **LGTM (APPROVED)** (代码变更干净，未发现风险)"

        lines = [
            "## 🤖 Code Analysis Agent - PR 审查报告",
            "",
            f"**审查结论**: {status_badge}",
            f"**变更文件数**: {len(changed_files)} | **发现隐患**: {len(all_findings)} 处",
            "",
            "| 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🔵 LOW |",
            "|:---:|:---:|:---:|:---:|",
            f"| {crit} | {high} | {med} | {low} |",
            "",
        ]

        # Blast radius warnings
        if blast_radii:
            lines.append("### 💥 变更影响传播分析 (Blast Radius)")
            lines.append("以下文件的修改将级联影响下游模块，请重点回归测试：")
            for src_f, targets in blast_radii.items():
                lines.append(f"- `{src_f}` 级联影响 **{len(targets)}** 个模块: {', '.join(f'`{t}`' for t in targets[:5])}")
                if len(targets) > 5:
                    lines.append(f"  *(及另外 {len(targets) - 5} 个依赖文件)*")
            lines.append("")

        # Finding details
        if all_findings:
            lines.append("### 🔍 审查发现详情")
            for i, f in enumerate(all_findings, start=1):
                lines.append(f"<details><summary><b>#{i} [{f.severity}] {f.title}</b> (<code>{f.file_path}:{f.line_number}</code>)</summary>")
                lines.append("")
                if f.snippet:
                    lines.append(f"```python\n# 相关代码\n{f.snippet}\n```")
                lines.append(f"**建议**: {f.recommendation}")
                lines.append("</details>")
                lines.append("")

        return "\n".join(lines)
