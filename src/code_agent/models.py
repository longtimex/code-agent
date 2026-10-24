"""Domain Models for the Code Analysis Agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    file_path: str
    line_number: int
    snippet: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "snippet": self.snippet,
            "recommendation": self.recommendation,
        }
