"""Automated Batch Remediation Engine.

Safely applies automated fixes for deterministic anti-patterns and security flaws
with automatic AST syntax verification and backup protection.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import AgentConfig
from .patcher import Patcher
from .security_rules import CodeRuleEngine


@dataclass
class FixResult:
    file_path: str
    rule_id: str
    old_snippet: str
    new_snippet: str
    success: bool
    error: str = ""


class BatchFixer:
    """Applies safe, deterministic automated fixes to codebases."""

    SAFE_FIX_RULES: Dict[str, Tuple[str, str]] = {
        "SEC-004": ("yaml.load(", "yaml.safe_load("),
        "SEC-008": ("verify=False", "verify=True"),
        "SEC-009": ("tempfile.mktemp()", "tempfile.NamedTemporaryFile().name"),
        "CODE-001": ("except:", "except Exception:"),
    }

    @classmethod
    def fix_file(cls, file_path: Path | str, backup: bool = True) -> List[FixResult]:
        p = Path(file_path)
        if not p.is_file() or p.suffix != ".py":
            return []

        findings = CodeRuleEngine.scan_file(p)
        results: List[FixResult] = []

        for f in findings:
            if f.rule_id in cls.SAFE_FIX_RULES:
                old_target, new_replacement = cls.SAFE_FIX_RULES[f.rule_id]
                content = p.read_text(encoding="utf-8", errors="replace")

                if old_target in content:
                    res = Patcher.apply_replacement(
                        file_path=p,
                        old_snippet=old_target,
                        new_snippet=new_replacement,
                        backup=backup,
                    )
                    results.append(
                        FixResult(
                            file_path=str(p),
                            rule_id=f.rule_id,
                            old_snippet=old_target,
                            new_snippet=new_replacement,
                            success=res["success"],
                            error=res.get("error", ""),
                        )
                    )

        return results

    @classmethod
    def fix_directory(cls, dir_path: Path | str, backup: bool = True) -> List[FixResult]:
        root = Path(dir_path)
        cfg = AgentConfig.load(root)
        excludes = set(cfg.ignore_paths)

        all_results: List[FixResult] = []
        for p in root.rglob("*.py"):
            if any(part in excludes for part in p.parts):
                continue
            all_results.extend(cls.fix_file(p, backup=backup))

        return all_results
