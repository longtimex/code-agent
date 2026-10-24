"""SARIF (Static Analysis Results Interchange Format) 2.1.0 Exporter.

Enables native integration with GitHub Code Scanning (Security Tab),
GitLab SAST, SonarQube, and VS Code SARIF viewers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding


class SARIFExporter:
    """Converts Findings to standard OASIS SARIF v2.1.0 JSON format."""

    SEVERITY_MAP = {
        "CRITICAL": "error",
        "HIGH": "error",
        "MEDIUM": "warning",
        "LOW": "note",
        "INFO": "note",
    }

    @classmethod
    def to_sarif_dict(cls, findings: List[Finding]) -> Dict[str, Any]:
        rules_map: Dict[str, Dict[str, Any]] = {}
        results = []

        for f in findings:
            level = cls.SEVERITY_MAP.get(f.severity, "warning")

            if f.rule_id not in rules_map:
                rules_map[f.rule_id] = {
                    "id": f.rule_id,
                    "name": f.rule_id,
                    "shortDescription": {"text": f.title},
                    "help": {"text": f.recommendation},
                    "defaultConfiguration": {"level": level},
                }

            result_entry = {
                "ruleId": f.rule_id,
                "level": level,
                "message": {"text": f"{f.title}: {f.recommendation}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": f.file_path.replace("\\", "/"),
                                "uriBaseId": "%SRCROOT%",
                            },
                            "region": {
                                "startLine": max(1, f.line_number),
                                "snippet": {"text": f.snippet},
                            },
                        }
                    }
                ],
            }
            results.append(result_entry)

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "code-agent",
                            "semanticVersion": "0.1.0",
                            "informationUri": "https://github.com/code-agent",
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }

    @classmethod
    def export(cls, findings: List[Finding], output_path: str | Path) -> Path:
        target = Path(output_path)
        sarif_data = cls.to_sarif_dict(findings)
        target.write_text(json.dumps(sarif_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return target
