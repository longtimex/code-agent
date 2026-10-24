"""Automated Code Patching & Auto-Fix Engine.

Generates unified diffs, applies code replacements safely with automatic backup
and AST syntax validation rollback.
"""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any, Dict, Optional


class Patcher:
    """Manages patch generation, validation, and safe application."""

    @staticmethod
    def create_unified_diff(
        original_text: str,
        modified_text: str,
        file_path: str = "target.py",
    ) -> str:
        orig_lines = original_text.splitlines(keepends=True)
        mod_lines = modified_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    @classmethod
    def apply_replacement(
        cls,
        file_path: Path | str,
        old_snippet: str,
        new_snippet: str,
        backup: bool = True,
    ) -> Dict[str, Any]:
        """Replaces old_snippet with new_snippet, verifying syntax integrity."""
        p = Path(file_path)
        if not p.is_file():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        content = p.read_text(encoding="utf-8", errors="replace")
        old_normalized = old_snippet.strip()

        # Find occurrence
        if old_normalized not in content and old_snippet not in content:
            return {
                "success": False,
                "error": "The target snippet was not found in the file content.",
            }

        target_replace = old_snippet if old_snippet in content else old_normalized
        modified = content.replace(target_replace, new_snippet, 1)

        # Syntax check for Python files
        if p.suffix == ".py":
            try:
                ast.parse(modified, filename=str(p))
            except SyntaxError as e:
                return {
                    "success": False,
                    "error": f"Syntax validation failed after replacement: {e.msg} at line {e.lineno}",
                }

        backup_file = None
        if backup:
            backup_file = p.with_suffix(p.suffix + ".bak")
            backup_file.write_text(content, encoding="utf-8")

        p.write_text(modified, encoding="utf-8")
        diff_str = cls.create_unified_diff(content, modified, file_path=str(p.name))

        return {
            "success": True,
            "diff": diff_str,
            "backup_file": str(backup_file) if backup_file else None,
        }

    @classmethod
    def revert_backup(cls, file_path: Path | str) -> bool:
        p = Path(file_path)
        backup = p.with_suffix(p.suffix + ".bak")
        if backup.is_file():
            p.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
            backup.unlink()
            return True
        return False
