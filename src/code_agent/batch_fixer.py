"""Automated Batch Remediation Engine.

Safely applies automated fixes for deterministic anti-patterns and security flaws
with automatic AST syntax verification and backup protection.

Fixes are located by the exact line number reported by the rule engine rather than
by naive substring search, so comments, string literals and unrelated occurrences
of the same token are never rewritten. The whole file is re-parsed before it is
written to disk; if any rewrite breaks the syntax tree, nothing is saved.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from .config import AgentConfig
from .models import Finding
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

        original = cls._read(p)
        if original is None:
            return []

        targets = cls._collect_targets(CodeRuleEngine.scan_file(p))
        if not targets:
            return []

        lines = original.splitlines(keepends=True)
        results = cls._rewrite_lines(p, lines, targets)
        if not results:
            return []

        modified = "".join(lines)
        if modified == original:
            return []

        # Whole-file syntax gate: abort the entire batch instead of persisting
        # a partially broken file.
        error = cls._syntax_error(modified, p)
        if error:
            return cls._mark_all_failed(results, error)

        cls._persist(p, original, modified, backup)
        return results

    @staticmethod
    def _read(p: Path) -> str | None:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    @classmethod
    def _collect_targets(cls, findings: List[Finding]) -> Dict[str, List[int]]:
        """Maps rule_id -> affected line numbers, deduplicated.

        The same line can be reported more than once (e.g. by both the AST
        visitor and the regex pass); deduping keeps each line from being
        rewritten repeatedly.
        """
        targets: Dict[str, List[int]] = {}
        for f in findings:
            if f.rule_id not in cls.SAFE_FIX_RULES:
                continue
            lines_for_rule = targets.setdefault(f.rule_id, [])
            if f.line_number not in lines_for_rule:
                lines_for_rule.append(f.line_number)
        return targets

    @classmethod
    def _rewrite_lines(
        cls,
        p: Path,
        lines: List[str],
        targets: Dict[str, List[int]],
    ) -> List[FixResult]:
        results: List[FixResult] = []
        for rule_id in sorted(targets):
            old_target, new_replacement = cls.SAFE_FIX_RULES[rule_id]
            for lineno in sorted(targets[rule_id]):
                if not 1 <= lineno <= len(lines):
                    continue
                line = lines[lineno - 1]
                if old_target not in line:
                    continue

                # `yaml.safe_load()` rejects the Loader argument, so rewriting
                # `yaml.load(x, Loader=...)` would emit a broken call.
                if rule_id == "SEC-004" and "Loader" in line:
                    results.append(FixResult(
                        file_path=str(p),
                        rule_id=rule_id,
                        old_snippet=line.strip(),
                        new_snippet=line.strip(),
                        success=False,
                        error="该调用显式传入了 Loader 参数，需人工改为 yaml.safe_load(...) 并移除 Loader。",
                    ))
                    continue

                lines[lineno - 1] = line.replace(old_target, new_replacement, 1)
                results.append(FixResult(
                    file_path=str(p),
                    rule_id=rule_id,
                    old_snippet=line.strip(),
                    new_snippet=lines[lineno - 1].strip(),
                    success=True,
                ))
        return results

    @staticmethod
    def _syntax_error(modified: str, p: Path) -> str | None:
        try:
            ast.parse(modified, filename=str(p))
        except SyntaxError as exc:
            return f"改写后 AST 语法校验失败: {exc.msg} (line {exc.lineno})"
        return None

    @staticmethod
    def _mark_all_failed(results: List[FixResult], error: str) -> List[FixResult]:
        for r in results:
            if r.success:
                r.success = False
                r.error = error
        return results

    @staticmethod
    def _persist(p: Path, original: str, modified: str, backup: bool) -> None:
        if backup:
            try:
                p.with_suffix(p.suffix + ".bak").write_text(original, encoding="utf-8")
            except OSError:
                pass
        p.write_text(modified, encoding="utf-8")

    @classmethod
    def fix_directory(cls, dir_path: Path | str, backup: bool = True) -> List[FixResult]:
        root = Path(dir_path)
        cfg = AgentConfig.load(root)
        excludes = set(cfg.ignore_paths)

        all_results: List[FixResult] = []
        for p in sorted(root.rglob("*.py")):
            if any(part in excludes for part in p.parts):
                continue
            all_results.extend(cls.fix_file(p, backup=backup))

        return all_results
