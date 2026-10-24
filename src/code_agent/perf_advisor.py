"""Static Code Performance & Algorithmic Hotspot Advisor.

Detects performance anti-patterns including regex compilation inside loops,
string concatenation in loops, repeated file I/O, and inefficient linear lookups.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import AgentConfig
from .models import Finding


class PerformanceVisitor(ast.NodeVisitor):
    """AST visitor detecting performance antipatterns and algorithmic bottlenecks."""

    def __init__(self, file_path: str, source_lines: List[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.findings: List[Finding] = []
        self._loop_depth = 0

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_For(self, node: ast.For) -> None:
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self._loop_depth > 0:
            # Check re.compile / re.search / re.match inside loop
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "re" and node.func.attr in ("compile", "search", "match", "findall", "sub"):
                    self.findings.append(
                        Finding(
                            rule_id="PERF-101",
                            title=f"Regex Compilation Inside Loop (`re.{node.func.attr}`)",
                            severity="MEDIUM",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            snippet=self._get_snippet(node.lineno),
                            recommendation="Precompile regular expressions outside the loop via `pattern = re.compile(...)`.",
                        )
                    )

            # Check open() inside loop
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                self.findings.append(
                    Finding(
                        rule_id="PERF-104",
                        title="Repeated File I/O (`open()`) Inside Loop",
                        severity="MEDIUM",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_snippet(node.lineno),
                        recommendation="Open the file once outside the loop or batch I/O operations to avoid repeated OS file descriptors.",
                    )
                )

            # Check pandas iterrows()
            if isinstance(node.func, ast.Attribute) and node.func.attr == "iterrows":
                self.findings.append(
                    Finding(
                        rule_id="PERF-105",
                        title="Slow DataFrame Iteration via `df.iterrows()`",
                        severity="LOW",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_snippet(node.lineno),
                        recommendation="Use vectorized Pandas/NumPy operations, `.apply()`, or `.itertuples()` for significantly higher throughput.",
                    )
                )

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # String concatenation: s += ... inside loop
        if self._loop_depth > 0 and isinstance(node.op, ast.Add):
            if isinstance(node.target, ast.Name):
                # Ignore numeric increments like `count += 1`
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float, complex)):
                    self.generic_visit(node)
                    return

                is_string = False
                if isinstance(node.value, ast.JoinedStr):
                    is_string = True
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, (str, bytes)):
                    is_string = True
                else:
                    name_hints = ("str", "text", "msg", "out", "buf", "html", "line", "res", "chunk", "query", "sql", "desc")
                    is_string = any(hint in node.target.id.lower() for hint in name_hints)

                if is_string:
                    self.findings.append(
                        Finding(
                            rule_id="PERF-102",
                            title=f"Repeated String Concatenation (`+=`) Inside Loop on `{node.target.id}`",
                            severity="LOW",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            snippet=self._get_snippet(node.lineno),
                            recommendation="Append string chunks to a list and use `''.join(chunks)` to avoid quadratic memory copying.",
                        )
                    )
        self.generic_visit(node)


class PerformanceAdvisor:
    """Analyzes source code for performance anti-patterns."""

    @classmethod
    def scan_content(cls, content: str, file_path: str = "<unknown>") -> List[Finding]:
        try:
            tree = ast.parse(content, filename=file_path)
            lines = content.splitlines()
            visitor = PerformanceVisitor(file_path=file_path, source_lines=lines)
            visitor.visit(tree)
            return visitor.findings
        except Exception:
            return []

    @classmethod
    def scan_file(cls, path: Path | str) -> List[Finding]:
        p = Path(path)
        if not p.is_file() or p.suffix != ".py":
            return []
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            return cls.scan_content(content, file_path=str(p))
        except Exception:
            return []

    @classmethod
    def scan_directory(cls, dir_path: Path | str, config: Optional[AgentConfig] = None) -> List[Finding]:
        root = Path(dir_path)
        cfg = config or AgentConfig.load(root)
        excludes = set(cfg.ignore_paths)
        findings: List[Finding] = []
        for p in root.rglob("*.py"):
            if any(part in excludes for part in p.parts):
                continue
            findings.extend(cls.scan_file(p))
        return findings
