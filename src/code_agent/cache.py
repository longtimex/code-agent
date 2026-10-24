"""Incremental Analysis Cache Module.

Uses SHA-256 content hashing to avoid re-scanning unmodified files,
dramatically improving analysis speed on large codebases.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import Finding


class IncrementalCache:
    """Manages hash-based caching of file analysis results."""

    CACHE_FILENAME = ".code-agent-cache.json"

    def __init__(self, root_dir: Optional[Path | str] = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.cache_file = self.root_dir / self.CACHE_FILENAME
        self._entries: Dict[str, Dict[str, Any]] = {}
        self.load()

    @staticmethod
    def compute_hash(content_bytes: bytes) -> str:
        return hashlib.sha256(content_bytes).hexdigest()

    def load(self) -> None:
        if self.cache_file.is_file():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._entries = data
            except Exception:
                self._entries = {}

    def save(self) -> None:
        try:
            self.cache_file.write_text(
                json.dumps(self._entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get_cached(self, file_path: Path) -> Optional[List[Finding]]:
        rel_path = os.path.relpath(file_path, self.root_dir)
        entry = self._entries.get(rel_path)
        if not entry:
            return None

        try:
            current_hash = self.compute_hash(file_path.read_bytes())
            if current_hash == entry.get("hash"):
                from .models import Finding
                findings = []
                for f_dict in entry.get("findings", []):
                    findings.append(Finding(**f_dict))
                return findings
        except Exception:
            return None
        return None

    def update(self, file_path: Path, findings: List[Finding]) -> None:
        rel_path = os.path.relpath(file_path, self.root_dir)
        try:
            content_hash = self.compute_hash(file_path.read_bytes())
            self._entries[rel_path] = {
                "hash": content_hash,
                "findings": [f.to_dict() for f in findings],
            }
        except Exception:
            pass

    def clear(self) -> None:
        self._entries.clear()
        if self.cache_file.is_file():
            try:
                self.cache_file.unlink()
            except Exception:
                pass
