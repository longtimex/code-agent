"""Open-Source License & SPDX Compliance Auditor.

Detects SPDX license identifiers, scans repo LICENSE files, checks package
manifests, and flags copyleft license contagion risks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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

    @classmethod
    def audit(cls, root_dir: Path | str) -> LicenseReport:
        root = Path(root_dir)
        detected: Set[str] = set()
        warnings: List[str] = []
        files_with_spdx = 0
        total_scanned = 0

        # 1. Check for LICENSE / COPYING file
        license_file_name = None
        for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt"):
            p = root / name
            if p.is_file():
                license_file_name = name
                content = p.read_text(encoding="utf-8", errors="replace")
                if "MIT" in content:
                    detected.add("MIT")
                elif "Apache" in content:
                    detected.add("Apache-2.0")
                elif "General Public License" in content:
                    detected.add("GPL-3.0")
                elif "Affero" in content:
                    detected.add("AGPL-3.0")
                break

        # 2. Check pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            text = pyproject.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"""license\s*=\s*['"]([^'"]+)['"]""", text)
            if m:
                detected.add(m.group(1))

        # 3. Scan files for SPDX headers
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in (".git", ".venv", "__pycache__", "node_modules", "dist", "build") for part in p.parts):
                continue
            if p.suffix in (".py", ".js", ".ts", ".go", ".sh", ".c", ".cpp"):
                total_scanned += 1
                try:
                    head = "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[:15])
                    m = SPDX_PATTERN.search(head)
                    if m:
                        lic = m.group(1)
                        detected.add(lic)
                        files_with_spdx += 1
                except Exception:
                    pass

        # 4. Evaluate Copyleft risks
        for lic in detected:
            if any(cl.lower() in lic.lower() for cl in COPYLEFT_LICENSES):
                warnings.append(
                    f"⚠️ 检测到强传染性开源协议 `{lic}`！若本项目用于商业闭源软件，分发时可能具有开源代码传染风险。"
                )

        if not license_file_name and not detected:
            warnings.append("⚠️ 未在项目根目录检测到 LICENSE 文件，且未发现 SPDX 许可证声明。")

        return LicenseReport(
            detected_licenses=sorted(list(detected)),
            has_license_file=bool(license_file_name),
            license_file_name=license_file_name,
            files_with_spdx=files_with_spdx,
            total_files_scanned=total_scanned,
            risk_warnings=warnings,
        )
