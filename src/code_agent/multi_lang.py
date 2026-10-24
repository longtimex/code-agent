"""Multi-Language Code Parsing & Vulnerability Scanning Module.

Extends analysis capabilities to JavaScript, TypeScript, Go, and Shell scripts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import Finding

# Language Rule Patterns: (regex, rule_id, title, severity, recommendation)
JS_TS_RULES: List[Tuple[re.Pattern, str, str, str, str]] = [
    (
        re.compile(r"""(?:innerHTML|outerHTML|dangerouslySetInnerHTML)\s*="""),
        "SEC-JS-001",
        "DOM XSS via `innerHTML` / `dangerouslySetInnerHTML`",
        "HIGH",
        "Use `textContent`, `innerText`, or sanitization libraries like DOMPurify to prevent XSS.",
    ),
    (
        re.compile(r"""\b(?:eval|Function)\s*\("""),
        "SEC-JS-002",
        "Arbitrary Code Execution via `eval()` or `Function()` constructor",
        "CRITICAL",
        "Avoid dynamic JavaScript execution. Parse JSON data using `JSON.parse()`.",
    ),
    (
        re.compile(r"""(?:\bchild_process|[a-zA-Z0-9_]*cp)\.(?:exec|execSync)\s*\("""),
        "SEC-JS-003",
        "Command Injection Risk via `child_process.exec()`",
        "HIGH",
        "Use `child_process.execFile()` or `child_process.spawn()` with discrete arguments.",
    ),
    (
        re.compile(r"""jwt\.decode\s*\("""),
        "SEC-JS-004",
        "Unverified JWT Token Parsing via `jwt.decode()`",
        "MEDIUM",
        "Use `jwt.verify()` with secret or public key rather than unverified decoding.",
    ),
    (
        re.compile(r"""origin:\s*['"]\*['"]"""),
        "SEC-JS-005",
        "Overly Permissive CORS Configuration (`origin: '*'`)",
        "LOW",
        "Restrict CORS origins to specific trusted domains.",
    ),
]

GO_RULES: List[Tuple[re.Pattern, str, str, str, str]] = [
    (
        re.compile(r"""InsecureSkipVerify\s*:\s*true"""),
        "SEC-GO-001",
        "TLS Certificate Verification Disabled (`InsecureSkipVerify: true`)",
        "HIGH",
        "Enable TLS certificate verification to avoid Man-In-The-Middle attacks.",
    ),
    (
        re.compile(r"""(?:Query|Exec|QueryRow)\s*\(\s*fmt\.Sprintf"""),
        "SEC-GO-002",
        "SQL Injection via `fmt.Sprintf` in Database Query",
        "CRITICAL",
        "Use parameterized queries with placeholder parameters (`?` or `$1`), not string formatting.",
    ),
    (
        re.compile(r"""exec\.Command\s*\(\s*["'](?:sh|bash)["']\s*,\s*["']-c["']"""),
        "SEC-GO-003",
        "Shell Injection Risk in `exec.Command`",
        "HIGH",
        "Pass arguments directly to target binary without wrapping in a shell.",
    ),
]

SHELL_RULES: List[Tuple[re.Pattern, str, str, str, str]] = [
    (
        re.compile(r"""(?:curl|wget)\s+[^|]+\|\s*(?:bash|sh)"""),
        "SEC-SH-001",
        "Piped Remote Script Execution (`curl | bash`)",
        "CRITICAL",
        "Download scripts, verify integrity/checksums, and inspect them before execution.",
    ),
    (
        re.compile(r"""rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+\$[A-Za-z0-9_]+"""),
        "SEC-SH-002",
        "Unquoted Variable in `rm -rf` Command",
        "CRITICAL",
        "Quote variables (`\"$VAR\"`) and verify they are non-empty to avoid accidental root deletion.",
    ),
    (
        re.compile(r"""\beval\s+["']?\$"""),
        "SEC-SH-003",
        "Arbitrary Shell Command Execution via `eval`",
        "HIGH",
        "Avoid `eval` on dynamic variables in shell scripts.",
    ),
]


class MultiLangScanner:
    """Detects vulnerabilities and anti-patterns across multiple programming languages."""

    SUPPORTED_EXTENSIONS = {
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".go": "Go",
        ".sh": "Shell",
        ".bash": "Shell",
    }

    @classmethod
    def is_supported(cls, file_path: Path | str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_rules_for_file(cls, file_path: Path | str) -> List[Tuple[re.Pattern, str, str, str, str]]:
        ext = Path(file_path).suffix.lower()
        if ext in (".js", ".jsx", ".ts", ".tsx"):
            return JS_TS_RULES
        elif ext == ".go":
            return GO_RULES
        elif ext in (".sh", ".bash"):
            return SHELL_RULES
        return []

    @classmethod
    def scan_content(cls, content: str, file_path: str = "<unknown>") -> List[Finding]:
        rules = cls.get_rules_for_file(file_path)
        if not rules:
            return []

        lines = content.splitlines()
        findings: List[Finding] = []

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip single-line comments
            if stripped.startswith(("//", "#", "/*")):
                continue

            for pattern, rule_id, title, severity, rec in rules:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            title=title,
                            severity=severity,
                            file_path=file_path,
                            line_number=lineno,
                            snippet=stripped,
                            recommendation=rec,
                        )
                    )

        return findings

    @classmethod
    def extract_skeleton(cls, content: str, file_path: str = "") -> str:
        """Extracts high-level signatures from non-Python source files."""
        ext = Path(file_path).suffix.lower()
        lines = content.splitlines()
        skeleton_lines = []

        # JS/TS regex
        if ext in (".js", ".jsx", ".ts", ".tsx"):
            pattern = re.compile(
                r"""^\s*(?:export\s+)?(?:async\s+)?(?:function\*?|class|interface|type|const\s+[A-Za-z0-9_]+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"""
            )
            for line in lines:
                if pattern.search(line):
                    skeleton_lines.append(line.rstrip("{ \t") + " { ... }")

        # Go regex
        elif ext == ".go":
            pattern = re.compile(r"""^\s*(?:func\s+\([^)]+\)\s+[A-Za-z0-9_]+|func\s+[A-Za-z0-9_]+|type\s+[A-Za-z0-9_]+\s+(?:struct|interface))""")
            for line in lines:
                if pattern.search(line):
                    skeleton_lines.append(line.rstrip("{ \t") + " { ... }")

        # Shell regex
        elif ext in (".sh", ".bash"):
            pattern = re.compile(r"""^\s*(?:function\s+)?[A-Za-z0-9_-]+\s*\(\)\s*\{?""")
            for line in lines:
                if pattern.search(line):
                    skeleton_lines.append(line.strip())

        return "\n".join(skeleton_lines) if skeleton_lines else "# [Outline not available for this format]"
