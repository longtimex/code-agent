"""Automated Pull Request (PR) Review Generator.

Produces comprehensive, GitHub-ready PR review comments with blast radius warnings,
severity breakdown, and code suggestions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .call_graph import DependencyGraph
from .config import AgentConfig
from .git_tools import FileDiff, GitTools
from .models import Finding
from .security_rules import CodeRuleEngine

NO_CHANGES_MESSAGE = (
    "## 🤖 Code Analysis Agent - PR 审查报告\n\n"
    "✅ 没有检测到任何待审查的代码变更。\n\n"
    "> 提示: 请先提交或暂存改动，或使用 `--ref` 指定比较基准后再生成 PR 审查评论。"
)


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
            return NO_CHANGES_MESSAGE

        file_diffs = GitTools.parse_unified_diff(GitTools.get_diff(repo_path=root, ref=ref))
        findings, blast_radii = cls._collect(root, file_diffs)
        counts = cls._severity_counts(findings)

        lines = [
            "## 🤖 Code Analysis Agent - PR 审查报告",
            "",
            f"**审查结论**: {cls._status_badge(counts)}",
            f"**变更文件数**: {len(changed_files)} | **发现隐患**: {len(findings)} 处",
            "",
            "| 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🔵 LOW |",
            "|:---:|:---:|:---:|:---:|",
            f"| {counts['CRITICAL']} | {counts['HIGH']} | {counts['MEDIUM']} | {counts['LOW']} |",
            "",
        ]
        lines.extend(cls._blast_radius_section(blast_radii))
        lines.extend(cls._findings_section(findings))
        return "\n".join(lines)

    @classmethod
    def _collect(
        cls,
        root: Path,
        file_diffs: List[FileDiff],
    ) -> Tuple[List[Finding], Dict[str, List[str]]]:
        """Scans changed files and records the downstream blast radius per file."""
        config = AgentConfig.load(root)
        graph = DependencyGraph(root_dir=root)
        findings: List[Finding] = []
        blast_radii: Dict[str, List[str]] = {}

        for fd in file_diffs:
            target = root / fd.new_path
            if not target.is_file():
                continue
            file_findings = CodeRuleEngine.scan_file(target, config=config)
            findings.extend(cls._keep_changed_lines(file_findings, fd.changed_line_numbers))

            affected = graph.get_blast_radius(fd.new_path)
            if affected:
                blast_radii[fd.new_path] = affected

        return findings, blast_radii

    @staticmethod
    def _keep_changed_lines(findings: List[Finding], changed_lines: List[int]) -> List[Finding]:
        """Restricts findings to the lines touched by the diff (all findings if unknown)."""
        changed = set(changed_lines)
        if not changed:
            return findings
        return [f for f in findings if f.line_number in changed]

    @staticmethod
    def _severity_counts(findings: List[Finding]) -> Dict[str, int]:
        return {
            "CRITICAL": sum(1 for f in findings if f.severity == "CRITICAL"),
            "HIGH": sum(1 for f in findings if f.severity == "HIGH"),
            "MEDIUM": sum(1 for f in findings if f.severity == "MEDIUM"),
            "LOW": sum(1 for f in findings if f.severity in ("LOW", "INFO")),
        }

    @staticmethod
    def _status_badge(counts: Dict[str, int]) -> str:
        if counts["CRITICAL"]:
            return "❌ **CHANGES REQUESTED** (发现致命阻断隐患)"
        if counts["HIGH"]:
            return "⚠️ **NEEDS ATTENTION** (存在高风险安全缺陷)"
        if counts["MEDIUM"] or counts["LOW"]:
            return "🟡 **APPROVED WITH SUGGESTIONS** (建议优化反模式)"
        return "✅ **LGTM (APPROVED)** (代码变更干净，未发现风险)"

    @staticmethod
    def _blast_radius_section(blast_radii: Dict[str, List[str]]) -> List[str]:
        if not blast_radii:
            return []

        lines = [
            "### 💥 变更影响传播分析 (Blast Radius)",
            "以下文件的修改将级联影响下游模块，请重点回归测试：",
        ]
        for src_file, targets in blast_radii.items():
            preview = ", ".join(f"`{t}`" for t in targets[:5])
            lines.append(f"- `{src_file}` 级联影响 **{len(targets)}** 个模块: {preview}")
            if len(targets) > 5:
                lines.append(f"  *(及另外 {len(targets) - 5} 个依赖文件)*")
        lines.append("")
        return lines

    @staticmethod
    def _findings_section(findings: List[Finding]) -> List[str]:
        if not findings:
            return []

        lines = ["### 🔍 审查发现详情"]
        for i, f in enumerate(findings, start=1):
            lines.append(
                f"<details><summary><b>#{i} [{f.severity}] {f.title}</b> "
                f"(<code>{f.file_path}:{f.line_number}</code>)</summary>"
            )
            lines.append("")
            if f.snippet:
                lines.append(f"```python\n# 相关代码\n{f.snippet}\n```")
            lines.append(f"**建议**: {f.recommendation}")
            lines.append("</details>")
            lines.append("")
        return lines
