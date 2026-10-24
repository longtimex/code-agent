"""User-Defined & Team Custom Rules Engine.

Allows organizations to declare custom regex patterns and architectural policies
in `.code-agent.json` or `custom_rules.json`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Finding


@dataclass
class CustomRule:
    rule_id: str
    pattern: str
    title: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    recommendation: str
    file_extensions: List[str]  # e.g. ['.py', '.js']

    def matches(self, line: str) -> bool:
        try:
            return bool(re.search(self.pattern, line, re.IGNORECASE))
        except Exception:
            return False


class CustomRuleLoader:
    """Loads and executes team-specific custom rules."""

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> List[CustomRule]:
        rules = []
        for r in data.get("custom_rules", []):
            rules.append(
                CustomRule(
                    rule_id=r.get("id", "CUSTOM-001"),
                    pattern=r.get("pattern", ""),
                    title=r.get("title", "Custom Policy Violation"),
                    severity=r.get("severity", "MEDIUM"),
                    recommendation=r.get("recommendation", "Adhere to internal coding guidelines."),
                    file_extensions=r.get("file_extensions", [".py"]),
                )
            )
        return rules

    @classmethod
    def load_from_file(cls, path: Path | str) -> List[CustomRule]:
        p = Path(path)
        if not p.is_file():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls.load_from_dict(data)
        except Exception:
            return []

    @classmethod
    def scan_content(
        cls,
        content: str,
        file_path: str,
        rules: List[CustomRule],
    ) -> List[Finding]:
        if not rules:
            return []

        ext = Path(file_path).suffix.lower()
        applicable = [r for r in rules if not r.file_extensions or ext in r.file_extensions]
        if not applicable:
            return []

        findings: List[Finding] = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("#", "//", "/*")):
                continue

            for r in applicable:
                if r.matches(line):
                    findings.append(
                        Finding(
                            rule_id=r.rule_id,
                            title=r.title,
                            severity=r.severity,
                            file_path=file_path,
                            line_number=lineno,
                            snippet=stripped,
                            recommendation=r.recommendation,
                        )
                    )
        return findings
