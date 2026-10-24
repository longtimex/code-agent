"""Cross-file Dependency & Call Graph Engine.

Builds project-wide dependency topologies, traces symbol callers across modules,
and computes impact radius (blast radius) for code modifications.
"""

from __future__ import annotations

import ast
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .ast_parser import ASTParser


@dataclass
class CallLocation:
    caller_file: str
    caller_function: str
    target_symbol: str
    line_number: int


class DependencyGraph:
    """Builds and analyzes module dependencies and symbol relationships."""

    def __init__(self, root_dir: Optional[Path | str] = None) -> None:
        # Resolve up-front: Windows 8.3 short paths (e.g. `OVERGA~1`) expand to
        # long paths on `.resolve()`, so an unresolved root_dir would make every
        # `os.path.relpath()` in get_blast_radius() produce bogus `../..` keys.
        self.root_dir = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()
        # file -> set of imported files (relative paths)
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        # file -> set of files importing this file
        self.dependents: Dict[str, Set[str]] = defaultdict(set)
        # symbol -> list of definitions
        self.symbol_table: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # all known python files
        self.files: List[Path] = []
        self._build_index()

    def _build_index(self) -> None:
        excludes = {".git", ".venv", "__pycache__", "build", "dist", "node_modules"}
        self.files = [
            p for p in self.root_dir.rglob("*.py")
            if not any(part in excludes for part in p.parts)
        ]

        # First pass: index symbols
        for p in self.files:
            rel = os.path.relpath(p, self.root_dir)
            symbols = ASTParser.parse_file(p)
            for s in symbols:
                self.symbol_table[s.name].append({
                    "file": rel,
                    "kind": s.kind,
                    "line": s.start_line,
                    "signature": s.signature,
                })

        # Second pass: analyze imports and file dependencies
        for p in self.files:
            rel = os.path.relpath(p, self.root_dir)
            self._analyze_file_imports(p, rel)

    def _analyze_file_imports(self, file_path: Path, rel_path: str) -> None:
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._link_import(rel_path, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._link_import(rel_path, node.module, level=node.level, source_file=file_path)

    def _link_import(
        self,
        current_rel: str,
        module_name: str,
        level: int = 0,
        source_file: Optional[Path] = None,
    ) -> None:
        # Resolve relative import
        if level > 0 and source_file:
            target_dir = source_file.parent
            for _ in range(level - 1):
                target_dir = target_dir.parent
            candidate = target_dir / f"{module_name.replace('.', '/')}.py"
            if candidate.is_file():
                dep_rel = os.path.relpath(candidate, self.root_dir)
                self.dependencies[current_rel].add(dep_rel)
                self.dependents[dep_rel].add(current_rel)
                return

        # Resolve absolute / top-level module within repo
        mod_rel_path = module_name.replace(".", "/") + ".py"
        # Search among project files
        for f in self.files:
            f_rel = os.path.relpath(f, self.root_dir)
            if f_rel.endswith(mod_rel_path) or f_rel == mod_rel_path:
                self.dependencies[current_rel].add(f_rel)
                self.dependents[f_rel].add(current_rel)
                return

    def find_callers(self, symbol_name: str) -> List[CallLocation]:
        """Finds all locations where `symbol_name` is invoked."""
        callers: List[CallLocation] = []

        for p in self.files:
            rel = os.path.relpath(p, self.root_dir)
            symbols = ASTParser.parse_file(p)
            for sym in symbols:
                if symbol_name in sym.calls:
                    callers.append(
                        CallLocation(
                            caller_file=rel,
                            caller_function=sym.name,
                            target_symbol=symbol_name,
                            line_number=sym.start_line,
                        )
                    )
        return callers

    def get_blast_radius(self, file_path: str) -> List[str]:
        """Computes all files transitively dependent on `file_path`."""
        target_path = Path(file_path)
        if not target_path.is_absolute():
            target_path = (self.root_dir / target_path).resolve()
        target_rel = os.path.relpath(target_path, self.root_dir)
        visited: Set[str] = set()
        queue: deque[str] = deque([target_rel])

        while queue:
            curr = queue.popleft()
            for dep in self.dependents.get(curr, []):
                if dep not in visited and dep != target_rel:
                    visited.add(dep)
                    queue.append(dep)

        return sorted(list(visited))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": len(self.files),
            "dependencies": {k: sorted(list(v)) for k, v in self.dependencies.items()},
            "dependents": {k: sorted(list(v)) for k, v in self.dependents.items()},
        }
