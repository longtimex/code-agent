"""Technical Debt & Code Maintainability Metrics Engine.

Calculates Maintainability Index (MI), estimated debt remediation hours,
and detects cross-file duplicate code blocks (clone detection).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .ast_parser import ASTParser
from .config import AgentConfig
from .models import Finding
from .security_rules import CodeRuleEngine


@dataclass
class DuplicateBlock:
    line_count: int
    instances: List[Tuple[str, int, int]]  # (file_path, start_line, end_line)
    sample_content: str


@dataclass
class TechnicalDebtReport:
    total_files: int
    total_loc: int
    maintainability_index: float
    maintainability_grade: str  # 'A', 'B', 'C', 'D'
    total_debt_hours: float
    total_findings: int
    duplicates_count: int
    duplicates: List[DuplicateBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_loc": self.total_loc,
            "maintainability_index": round(self.maintainability_index, 1),
            "maintainability_grade": self.maintainability_grade,
            "total_debt_hours": round(self.total_debt_hours, 1),
            "total_findings": self.total_findings,
            "duplicates_count": self.duplicates_count,
            "duplicates": [
                {
                    "lines": d.line_count,
                    "occurrences": len(d.instances),
                    "locations": [f"{f}:{s}-{e}" for f, s, e in d.instances],
                }
                for d in self.duplicates
            ],
        }


class DebtEstimator:
    """Computes technical debt, maintainability index, and duplicate code."""

    REMEDIATION_HOURS = {
        "CRITICAL": 2.0,
        "HIGH": 1.0,
        "MEDIUM": 0.5,
        "LOW": 0.25,
        "INFO": 0.1,
    }

    @classmethod
    def calculate_maintainability_index(cls, loc: int, complexity: int) -> Tuple[float, str]:
        if loc <= 0:
            return 100.0, "A"

        # Simplified Radon/SEI formula
        vol = max(1.0, float(loc * 8))
        raw_mi = 171.0 - 5.2 * math.log(vol) - 0.23 * float(complexity) - 16.2 * math.log(float(loc))
        # Normalize to 0 - 100 scale
        normalized_mi = max(0.0, min(100.0, (raw_mi * 100.0) / 171.0))

        if normalized_mi >= 60:
            grade = "A"
        elif normalized_mi >= 40:
            grade = "B"
        elif normalized_mi >= 20:
            grade = "C"
        else:
            grade = "D"

        return normalized_mi, grade

    @classmethod
    def find_duplicates(
        cls,
        files: List[Path],
        min_lines: int = 5,
    ) -> List[DuplicateBlock]:
        """Detects identical blocks of consecutive code lines across files."""
        chunk_map: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)

        for p in files:
            try:
                raw_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            cleaned = []
            orig_linenos = []
            for lineno, l in enumerate(raw_lines, start=1):
                s = l.strip()
                if s and not s.startswith(("#", "//", "/*")):
                    cleaned.append(s)
                    orig_linenos.append(lineno)

            if len(cleaned) < min_lines:
                continue

            for i in range(len(cleaned) - min_lines + 1):
                chunk_str = "\n".join(cleaned[i : i + min_lines])
                start_l = orig_linenos[i]
                end_l = orig_linenos[i + min_lines - 1]
                chunk_map[chunk_str].append((str(p), start_l, end_l))

        duplicates = []
        for chunk, occurrences in chunk_map.items():
            if len(occurrences) > 1:
                # Deduplicate same file overlapping reports
                duplicates.append(
                    DuplicateBlock(
                        line_count=min_lines,
                        instances=occurrences,
                        sample_content=chunk,
                    )
                )

        # Sort by occurrences descending
        duplicates.sort(key=lambda d: len(d.instances), reverse=True)
        return duplicates[:10]  # top 10

    @classmethod
    def analyze(cls, root_dir: Path | str) -> TechnicalDebtReport:
        root = Path(root_dir)
        cfg = AgentConfig.load(root)
        excludes = set(cfg.ignore_paths)

        files = [
            p for p in root.rglob("*.py")
            if not any(part in excludes for part in p.parts)
        ]

        total_loc = 0
        total_complexity = 0

        file_mis = []
        for f in files:
            try:
                f_text = f.read_text(encoding="utf-8", errors="replace")
                f_loc = len(f_text.splitlines())
                total_loc += f_loc
                symbols = ASTParser.parse_file(f)
                f_comp = sum(s.complexity for s in symbols)
                total_complexity += f_comp
                if f_loc > 0:
                    f_mi, _ = cls.calculate_maintainability_index(f_loc, f_comp)
                    file_mis.append(f_mi)
            except Exception:
                pass

        avg_mi = sum(file_mis) / len(file_mis) if file_mis else 100.0
        if avg_mi >= 60:
            grade = "A"
        elif avg_mi >= 40:
            grade = "B"
        elif avg_mi >= 20:
            grade = "C"
        else:
            grade = "D"
        mi = avg_mi

        findings = CodeRuleEngine.scan_directory(root, config=cfg)
        total_debt_hours = sum(cls.REMEDIATION_HOURS.get(f.severity, 0.25) for f in findings)

        duplicates = cls.find_duplicates(files, min_lines=5)

        return TechnicalDebtReport(
            total_files=len(files),
            total_loc=total_loc,
            maintainability_index=mi,
            maintainability_grade=grade,
            total_debt_hours=total_debt_hours,
            total_findings=len(findings),
            duplicates_count=len(duplicates),
            duplicates=duplicates,
        )
