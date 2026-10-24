"""Open-Source License & SPDX Compliance Auditor.

Detects SPDX license identifiers, scans repo LICENSE files, checks package
manifests, and flags copyleft license contagion risks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SPDX_PATTERN = re.compile(r"""SPDX-License-Identifier:\s*([A-Za-z0-9\.\-\+]+)""", re.IGNORECASE)

COPYLEFT_LICENSES = {
    "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "GPL-2.0", "GPL-3.0", "GPL-2.0-only", "GPL-3.0-only",
    "SSPL", "CC-BY-NC-SA",
}

PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense",
}


@dataclass
class LicenseReport:
    detected_licenses: List[str]
    has_license_file: bool
    license_file_name: Optional[str]
    files_with_spdx: int
    total_files_scanned: int
    risk_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_licenses": self.detected_licenses,
            "has_license_file": self.has_license_file,
            "license_file": self.license_file_name,
            "spdx_annotated_files": self.files_with_spdx,
            "total_files": self.total_files_scanned,
            "risk_warnings": self.risk_warnings,
        }


class LicenseChecker:
    """Audits open-source license compliance across a codebase."""

    LICENSE_FILENAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt")
    EXCLUDED_DIRS = (".git", ".venv", "__pycache__", "node_modules", "dist", "build")
    SOURCE_SUFFIXES = (".py", ".js", ".ts", ".go", ".sh", ".c", ".cpp")

    @classmethod
    def audit(cls, root_dir: Path | str) -> LicenseReport:
        root = Path(root_dir)

        license_file_name, detected = cls._detect_license_file(root)
        detected |= cls._detect_from_pyproject(root)
        spdx_files, total_scanned, spdx_licenses = cls._scan_spdx_headers(root)
        detected |= spdx_licenses

        warnings = cls._copyleft_warnings(detected)
        if not license_file_name and not detected:
            warnings.append("⚠️ 未在项目根目录检测到 LICENSE 文件，且未发现 SPDX 许可证声明。")

        return LicenseReport(
            detected_licenses=sorted(detected),
            has_license_file=bool(license_file_name),
            license_file_name=license_file_name,
            files_with_spdx=spdx_files,
            total_files_scanned=total_scanned,
            risk_warnings=warnings,
        )

    @classmethod
    def _detect_license_file(cls, root: Path) -> Tuple[Optional[str], Set[str]]:
        """Finds the first LICENSE/COPYING file and classifies its text."""
        for name in cls.LICENSE_FILENAMES:
            candidate = root / name
            if not candidate.is_file():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return name, set()
            return name, cls._classify_license_text(content)
        return None, set()

    @staticmethod
    def _classify_license_text(content: str) -> Set[str]:
        # AGPL must be matched before plain GPL: its full name contains
        # "GNU Affero General Public License", which would otherwise be
        # reported as GPL-3.0.
        if "Affero" in content:
            return {"AGPL-3.0"}
        if "MIT" in content:
            return {"MIT"}
        if "Apache" in content:
            return {"Apache-2.0"}
        if "General Public License" in content:
            return {"GPL-3.0"}
        return set()

    @staticmethod
    def _detect_from_pyproject(root: Path) -> Set[str]:
        pyproject = root / "pyproject.toml"
        if not pyproject.is_file():
            return set()
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set()
        match = re.search(r"""license\s*=\s*['"]([^'"]+)['"]""", text)
        return {match.group(1)} if match else set()

    @classmethod
    def _scan_spdx_headers(cls, root: Path) -> Tuple[int, int, Set[str]]:
        """Counts source files carrying an SPDX header and collects their licenses."""
        files_with_spdx = 0
        total_scanned = 0
        licenses: Set[str] = set()

        for path in root.rglob("*"):
            if not cls._is_scannable(path):
                continue
            total_scanned += 1
            license_id = cls._read_spdx(path)
            if license_id:
                licenses.add(license_id)
                files_with_spdx += 1

        return files_with_spdx, total_scanned, licenses

    @classmethod
    def _is_scannable(cls, path: Path) -> bool:
        if not path.is_file():
            return False
        if any(part in cls.EXCLUDED_DIRS for part in path.parts):
            return False
        return path.suffix in cls.SOURCE_SUFFIXES

    @staticmethod
    def _read_spdx(path: Path) -> Optional[str]:
        """Reads the license identifier from the file header (first 15 lines)."""
        try:
            head = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:15])
        except OSError:
            return None
        match = SPDX_PATTERN.search(head)
        return match.group(1) if match else None

    @staticmethod
    def _copyleft_warnings(detected: Set[str]) -> List[str]:
        return [
            f"⚠️ 检测到强传染性开源协议 `{license_id}`！"
            "若本项目用于商业闭源软件，分发时可能具有开源代码传染风险。"
            for license_id in sorted(detected)
            if any(copyleft.lower() in license_id.lower() for copyleft in COPYLEFT_LICENSES)
        ]
