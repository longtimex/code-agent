"""Git integration and Diff parsing utilities."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

HUNK_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")


@dataclass
class DiffHunk:
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: List[str] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str
    new_path: str
    is_new: bool = False
    is_deleted: bool = False
    hunks: List[DiffHunk] = field(default_factory=list)

    @property
    def changed_line_numbers(self) -> List[int]:
        lines: List[int] = []
        for hunk in self.hunks:
            current_line = hunk.new_start
            for l in hunk.lines:
                if l.startswith("+") and not l.startswith("+++"):
                    lines.append(current_line)
                    current_line += 1
                elif l.startswith(" "):
                    current_line += 1
        return lines


class GitTools:
    """Provides git operations and diff parsing without external dependencies."""

    HUNK_PATTERN = HUNK_PATTERN

    @staticmethod
    def _run_git(args: List[str], cwd: Optional[Path | str] = None) -> str:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""

    @classmethod
    def get_repo_root(cls, start_path: Optional[str | Path] = None) -> Optional[Path]:
        out = cls._run_git(["rev-parse", "--show-toplevel"], cwd=start_path).strip()
        return Path(out) if out else None

    @classmethod
    def get_changed_files(cls, repo_path: Optional[str | Path] = None, ref: str = "HEAD") -> List[str]:
        out = cls._run_git(["status", "--porcelain"], cwd=repo_path)
        changed = set()
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path = parts[1].split(" -> ")[-1].strip()
                changed.add(path)

        if not changed:
            out = cls._run_git(["diff", "--name-only", f"{ref}~1", ref], cwd=repo_path)
            if not out:
                out = cls._run_git(["diff", "--name-only", ref], cwd=repo_path)
            for line in out.splitlines():
                if line.strip():
                    changed.add(line.strip())

        return sorted(list(changed))

    @classmethod
    def get_diff(
        cls,
        repo_path: Optional[str | Path] = None,
        ref: Optional[str] = None,
        cached: bool = False,
        file_path: Optional[str] = None,
    ) -> str:
        args = ["diff"]
        if cached:
            args.append("--cached")
        if ref:
            args.append(ref)
        if file_path:
            args.extend(["--", file_path])
        return cls._run_git(args, cwd=repo_path)

    @classmethod
    def parse_unified_diff(cls, diff_text: str) -> List[FileDiff]:
        parser = _UnifiedDiffParser()
        for line in diff_text.splitlines():
            parser.feed(line)
        return parser.finish()


class _UnifiedDiffParser:
    """Incremental unified-diff state machine.

    Keeping the per-line branching in dedicated methods keeps the public
    `parse_unified_diff` entry point trivially simple.
    """

    def __init__(self) -> None:
        self.file_diffs: List[FileDiff] = []
        self._current_diff: Optional[FileDiff] = None
        self._current_hunk: Optional[DiffHunk] = None

    def feed(self, line: str) -> None:
        if line.startswith("diff --git"):
            self._start_file(line)
        elif self._mark_file_flags(line):
            return
        elif line.startswith("@@"):
            self._start_hunk(line)
        elif self._current_hunk is not None:
            self._current_hunk.lines.append(line)

    def finish(self) -> List[FileDiff]:
        self._flush_diff()
        return self.file_diffs

    def _start_file(self, line: str) -> None:
        self._flush_diff()
        parts = line.split()
        old_p = parts[2].removeprefix("a/") if len(parts) > 2 else ""
        new_p = parts[3].removeprefix("b/") if len(parts) > 3 else ""
        self._current_diff = FileDiff(old_path=old_p, new_path=new_p)

    def _mark_file_flags(self, line: str) -> bool:
        if self._current_diff is None:
            return False
        if line.startswith("new file mode"):
            self._current_diff.is_new = True
            return True
        if line.startswith("deleted file mode"):
            self._current_diff.is_deleted = True
            return True
        return False

    def _start_hunk(self, line: str) -> None:
        self._flush_hunk()
        match = HUNK_PATTERN.match(line)
        if match and self._current_diff:
            self._current_hunk = DiffHunk(
                old_start=int(match.group(1)),
                old_lines=int(match.group(2) or 1),
                new_start=int(match.group(3)),
                new_lines=int(match.group(4) or 1),
                header=match.group(5).strip(),
                lines=[],
            )

    def _flush_hunk(self) -> None:
        if self._current_diff and self._current_hunk:
            self._current_diff.hunks.append(self._current_hunk)
        self._current_hunk = None

    def _flush_diff(self) -> None:
        self._flush_hunk()
        if self._current_diff:
            self.file_diffs.append(self._current_diff)
            self._current_diff = None
