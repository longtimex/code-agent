"""CI/CD & GitHub Actions Integration Module.

Emits GitHub Actions workflow commands (::error / ::warning) for inline PR annotations
and appends rich Markdown review summaries to $GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .models import Finding

GITHUB_WORKFLOW_TEMPLATE = """name: Code Agent Review & Security Audit

on:
  pull_request:
    branches: [ main, master, develop ]
  push:
    branches: [ main, master ]

jobs:
  code-audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Run Code Analysis Agent
        run: |
          python3 -m code_agent.cli scan . --ci-github
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
"""


class CIIntegration:
    """Formats findings for GitHub Actions and CI environments."""

    @classmethod
    def emit_github_annotations(cls, findings: List[Finding]) -> None:
        """Emits ::error and ::warning commands for GitHub PR line annotations."""
        for f in findings:
            cmd = "error" if f.severity in ("CRITICAL", "HIGH") else "warning"
            file_arg = f"file={f.file_path}"
            line_arg = f"line={f.line_number}"
            title_arg = f"title=[{f.severity}] {f.title} ({f.rule_id})"
            msg = f"{f.recommendation} | Code: {f.snippet}"
            print(f"::{cmd} {file_arg},{line_arg},{title_arg}::{msg}")

    @classmethod
    def write_step_summary(cls, findings: List[Finding]) -> None:
        """Appends Markdown summary to $GITHUB_STEP_SUMMARY if available."""
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return

        crit = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        med = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity == "LOW")

        lines = [
            "## 🛡️ Code Analysis Agent Audit Summary",
            "",
            f"**Total Findings**: {len(findings)}",
            "",
            f"- 🔴 **CRITICAL**: {crit}",
            f"- 🟠 **HIGH**: {high}",
            f"- 🟡 **MEDIUM**: {med}",
            f"- 🔵 **LOW**: {low}",
            "",
            "| Severity | Rule ID | Title | File & Line |",
            "|---|---|---|---|",
        ]

        for f in findings:
            lines.append(f"| **{f.severity}** | `{f.rule_id}` | {f.title} | `{f.file_path}:{f.line_number}` |")

        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        except Exception:
            pass

    @classmethod
    def generate_workflow_file(cls, root_dir: Path | str = ".") -> Path:
        target_dir = Path(root_dir) / ".github" / "workflows"
        target_dir.mkdir(parents=True, exist_ok=True)
        wf_path = target_dir / "code-agent.yml"
        wf_path.write_text(GITHUB_WORKFLOW_TEMPLATE, encoding="utf-8")
        return wf_path
