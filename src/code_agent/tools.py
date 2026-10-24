"""Agent Tools Registry and Execution Engine.

Provides concrete tools callable by the LLM Agent to inspect code, search symbols,
run static checks, examine git diffs, analyze dependencies, and apply patches.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .ast_parser import ASTParser
from .call_graph import DependencyGraph
from .config import AgentConfig
from .git_tools import GitTools
from .patcher import Patcher
from .test_generator import TestGenerator
from .security_rules import CodeRuleEngine
from .batch_fixer import BatchFixer
from .doc_generator import DocGenerator
from .license_checker import LicenseChecker
from .perf_advisor import PerformanceAdvisor


class ToolRegistry:
    """Registry managing available tools and their JSON schemas for LLMs."""

    def __init__(self, workspace_root: Optional[Path | str] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.config = AgentConfig.load(self.workspace_root)
        self._dep_graph: Optional[DependencyGraph] = None
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._schemas: List[Dict[str, Any]] = []
        self._register_default_tools()

    @property
    def dep_graph(self) -> DependencyGraph:
        if self._dep_graph is None:
            self._dep_graph = DependencyGraph(root_dir=self.workspace_root)
        return self._dep_graph

    def register(self, name: str, description: str, parameters: Dict[str, Any], func: Callable[..., Any]) -> None:
        self._tools[name] = func
        self._schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })

    def get_schemas(self) -> List[Dict[str, Any]]:
        return self._schemas

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        if name not in self._tools:
            return json.dumps({"error": f"Tool '{name}' is not registered."})
        try:
            res = self._tools[name](**arguments)
            if isinstance(res, (dict, list)):
                return json.dumps(res, indent=2, ensure_ascii=False)
            return str(res)
        except Exception as e:
            return json.dumps({"error": f"Execution of '{name}' failed: {str(e)}"})

    def _resolve_path(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        return (self.workspace_root / p).resolve()

    def _register_default_tools(self) -> None:
        # 1. get_file_outline
        self.register(
            name="get_file_outline",
            description="Extracts class definitions, function signatures, docstrings, and complexity without full implementation bodies.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative or absolute path to Python file"},
                },
                "required": ["file_path"],
            },
            func=self.tool_get_file_outline,
        )

        # 2. read_symbol
        self.register(
            name="read_symbol",
            description="Fetches the complete source code of a specific function, method, or class by name.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "symbol_name": {"type": "string", "description": "Name of the function or class (e.g. 'my_func' or 'MyClass.my_method')"},
                },
                "required": ["file_path", "symbol_name"],
            },
            func=self.tool_read_symbol,
        )

        # 3. read_file_lines
        self.register(
            name="read_file_lines",
            description="Reads specific line range of a file with line numbers for detailed inspection.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "start_line": {"type": "integer", "description": "Starting line number (1-based)"},
                    "end_line": {"type": "integer", "description": "Ending line number (1-based)"},
                },
                "required": ["file_path", "start_line", "end_line"],
            },
            func=self.tool_read_file_lines,
        )

        # 4. search_code
        self.register(
            name="search_code",
            description="Searches for string patterns or regex matches across repository files.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex pattern to search"},
                    "file_pattern": {"type": "string", "description": "File glob pattern, e.g. '*.py'"},
                },
                "required": ["query"],
            },
            func=self.tool_search_code,
        )

        # 5. run_static_scan
        self.register(
            name="run_static_scan",
            description="Executes deterministic AST and regex security/quality rules on target file or directory.",
            parameters={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "description": "Path to file or folder to scan"},
                },
                "required": ["target_path"],
            },
            func=self.tool_run_static_scan,
        )

        # 6. get_git_diff
        self.register(
            name="get_git_diff",
            description="Retrieves git diff of current changes or comparison against a git reference.",
            parameters={
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Git ref to compare (default: HEAD)", "default": "HEAD"},
                    "file_path": {"type": "string", "description": "Optional specific file to restrict diff"},
                },
            },
            func=self.tool_get_git_diff,
        )

        # 7. find_symbol_callers
        self.register(
            name="find_symbol_callers",
            description="Finds all locations across the repository where a specific function or method is called.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol_name": {"type": "string", "description": "Name of function or method to trace"},
                },
                "required": ["symbol_name"],
            },
            func=self.tool_find_symbol_callers,
        )

        # 8. get_blast_radius
        self.register(
            name="get_blast_radius",
            description="Computes the impact radius: all files that directly or indirectly import the specified file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path of the modified file"},
                },
                "required": ["file_path"],
            },
            func=self.tool_get_blast_radius,
        )

        # 9. apply_code_patch
        self.register(
            name="apply_code_patch",
            description="Applies a code replacement fix to a file with automatic backup and syntax verification.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file to patch"},
                    "old_code": {"type": "string", "description": "Target code snippet to replace"},
                    "new_code": {"type": "string", "description": "New replacement code snippet"},
                },
                "required": ["file_path", "old_code", "new_code"],
            },
            func=self.tool_apply_code_patch,
        )

        # 10. generate_unit_tests
        self.register(
            name="generate_unit_tests",
            description="Automatically synthesizes pytest or unittest test cases covering edge cases for functions in a file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Target Python file path"},
                    "framework": {"type": "string", "description": "Testing framework ('pytest' or 'unittest')", "default": "pytest"},
                },
                "required": ["file_path"],
            },
            func=self.tool_generate_unit_tests,
        )

        # 11. check_performance
        self.register(
            name="check_performance",
            description="Analyzes Python source files or directories for performance bottlenecks, regex recompilation in loops, and inefficient I/O.",
            parameters={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "description": "Path to Python file or directory"},
                },
                "required": ["target_path"],
            },
            func=self.tool_check_performance,
        )

        # 12. generate_documentation
        self.register(
            name="generate_documentation",
            description="Generates Markdown documentation (API reference or Architecture topology) from AST and dependency call graph.",
            parameters={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "description": "Target file or directory path (default is workspace root)", "default": "."},
                    "doc_type": {"type": "string", "description": "'api', 'architecture', or 'both'", "default": "both"},
                },
            },
            func=self.tool_generate_documentation,
        )

        # 13. audit_licenses
        self.register(
            name="audit_licenses",
            description="Audits open-source license compliance, SPDX headers, and flags copyleft contagion risks.",
            parameters={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "description": "Path to workspace or directory to audit", "default": "."},
                },
            },
            func=self.tool_audit_licenses,
        )

        # 14. batch_fix_code
        self.register(
            name="batch_fix_code",
            description="Safely and automatically applies fixes for deterministic anti-patterns and security vulnerabilities with AST syntax verification.",
            parameters={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "description": "Target Python file or directory to remediate"},
                    "backup": {"type": "boolean", "description": "Whether to create .bak backup before modifying", "default": True},
                },
                "required": ["target_path"],
            },
            func=self.tool_batch_fix_code,
        )

    # Tool Implementations
    def tool_get_file_outline(self, file_path: str) -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        if not p.is_file():
            return {"error": f"File '{file_path}' does not exist"}
        content = p.read_text(encoding="utf-8", errors="replace")
        skeleton = ASTParser.get_skeleton(content)
        symbols = [s.to_dict() for s in ASTParser.parse_source(content, filename=str(p))]
        return {
            "file": file_path,
            "skeleton": skeleton,
            "symbols_count": len(symbols),
            "symbols": symbols,
        }

    def tool_read_symbol(self, file_path: str, symbol_name: str) -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        if not p.is_file():
            return {"error": f"File '{file_path}' does not exist"}
        content = p.read_text(encoding="utf-8", errors="replace")
        code = ASTParser.extract_symbol_source(content, symbol_name)
        if code is None:
            return {"error": f"Symbol '{symbol_name}' not found in '{file_path}'"}
        return {"file": file_path, "symbol": symbol_name, "code": code}

    def tool_read_file_lines(self, file_path: str, start_line: int, end_line: int) -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        if not p.is_file():
            return {"error": f"File '{file_path}' does not exist"}
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start_line)
        end = min(len(lines), end_line)
        selected = [f"{i}: {lines[i-1]}" for i in range(start, end + 1)]
        return {
            "file": file_path,
            "start_line": start,
            "end_line": end,
            "content": "\n".join(selected),
        }

    def tool_search_code(self, query: str, file_pattern: str = "*.py") -> List[Dict[str, Any]]:
        try:
            res = subprocess.run(
                ["rg", "-n", "--glob", file_pattern, query, str(self.workspace_root)],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode in (0, 1) and res.stdout:
                matches = []
                for line in res.stdout.splitlines()[:50]:
                    parts = line.split(":", 2)
                    if len(parts) == 3:
                        matches.append({
                            "file": os.path.relpath(parts[0], self.workspace_root),
                            "line": int(parts[1]),
                            "text": parts[2].strip(),
                        })
                return matches
        except Exception:
            pass

        results = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for p in self.workspace_root.rglob(file_pattern):
            if any(x in p.parts for x in self.config.ignore_paths):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                for lineno, line in enumerate(content.splitlines(), start=1):
                    if pattern.search(line):
                        results.append({
                            "file": os.path.relpath(p, self.workspace_root),
                            "line": lineno,
                            "text": line.strip(),
                        })
                        if len(results) >= 50:
                            return results
            except Exception:
                continue
        return results

    def tool_run_static_scan(self, target_path: str) -> Dict[str, Any]:
        p = self._resolve_path(target_path)
        if p.is_file():
            findings = CodeRuleEngine.scan_file(p, config=self.config)
        elif p.is_dir():
            findings = CodeRuleEngine.scan_directory(p, config=self.config)
        else:
            return {"error": f"Path '{target_path}' not found"}

        return {
            "target": target_path,
            "findings_count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }

    def tool_get_git_diff(self, ref: str = "HEAD", file_path: Optional[str] = None) -> Dict[str, Any]:
        diff = GitTools.get_diff(repo_path=self.workspace_root, ref=ref, file_path=file_path)
        changed = GitTools.get_changed_files(repo_path=self.workspace_root, ref=ref)
        return {
            "ref": ref,
            "changed_files": changed,
            "diff_snippet": diff[:4000] if diff else "",
            "diff_total_chars": len(diff),
        }

    def tool_find_symbol_callers(self, symbol_name: str) -> List[Dict[str, Any]]:
        callers = self.dep_graph.find_callers(symbol_name)
        return [
            {
                "file": c.caller_file,
                "caller_function": c.caller_function,
                "line": c.line_number,
            }
            for c in callers
        ]

    def tool_get_blast_radius(self, file_path: str) -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        affected = self.dep_graph.get_blast_radius(str(p))
        return {
            "target_file": file_path,
            "affected_files_count": len(affected),
            "affected_files": affected,
        }

    def tool_apply_code_patch(self, file_path: str, old_code: str, new_code: str) -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        return Patcher.apply_replacement(p, old_code, new_code, backup=True)

    def tool_generate_unit_tests(self, file_path: str, framework: str = "pytest") -> Dict[str, Any]:
        p = self._resolve_path(file_path)
        tests_code = TestGenerator.generate_test_file(p, output_framework=framework)
        return {
            "file": file_path,
            "framework": framework,
            "test_code_preview": tests_code[:1000],
            "total_chars": len(tests_code),
        }

    def tool_check_performance(self, target_path: str) -> Dict[str, Any]:
        p = self._resolve_path(target_path)
        if p.is_file():
            findings = PerformanceAdvisor.scan_file(p)
        elif p.is_dir():
            findings = PerformanceAdvisor.scan_directory(p, config=self.config)
        else:
            return {"error": f"Path '{target_path}' not found"}
        return {
            "target": target_path,
            "findings_count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }

    def tool_generate_documentation(self, target_path: str = ".", doc_type: str = "both") -> Dict[str, Any]:
        p = self._resolve_path(target_path)
        result: Dict[str, Any] = {"target": target_path}
        if doc_type in ("api", "both"):
            result["api_doc"] = DocGenerator.generate_api_doc(p)
        if doc_type in ("architecture", "both"):
            result["architecture_doc"] = DocGenerator.generate_architecture_doc(p if p.is_dir() else p.parent)
        return result

    def tool_audit_licenses(self, target_path: str = ".") -> Dict[str, Any]:
        p = self._resolve_path(target_path)
        report = LicenseChecker.audit(p if p.is_dir() else p.parent)
        return report.to_dict()

    def tool_batch_fix_code(self, target_path: str, backup: bool = True) -> Dict[str, Any]:
        p = self._resolve_path(target_path)
        if p.is_file():
            results = BatchFixer.fix_file(p, backup=backup)
        elif p.is_dir():
            results = BatchFixer.fix_directory(p, backup=backup)
        else:
            return {"error": f"Path '{target_path}' not found"}
        return {
            "target": target_path,
            "fixed_count": sum(1 for r in results if r.success),
            "results": [
                {
                    "file": r.file_path,
                    "rule_id": r.rule_id,
                    "old_snippet": r.old_snippet,
                    "new_snippet": r.new_snippet,
                    "success": r.success,
                    "error": r.error,
                }
                for r in results
            ],
        }
