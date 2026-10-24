"""Deterministic Static Analysis & Security Rules Engine.

Detects common vulnerabilities, anti-patterns, secrets, and excessive complexity
without needing heavy external dependencies.
"""

from __future__ import annotations

from .models import Finding

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ast_parser import ASTParser
from .config import AgentConfig
from .cache import IncrementalCache
from .multi_lang import MultiLangScanner


# Finding imported from .models


class SecurityScanner(ast.NodeVisitor):
    """Modular AST visitor detecting security vulnerabilities and anti-patterns."""

    def __init__(self, file_path: str, source_lines: List[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.findings: List[Finding] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_Call(self, node: ast.Call) -> None:
        self._check_dynamic_code_exec(node)
        self._check_os_and_subprocess(node)
        self._check_deserialization(node)
        self._check_weak_crypto(node)
        self._check_sql_injection(node)
        self._check_insecure_ssl(node)
        self._check_tempfile(node)
        self.generic_visit(node)

    def _check_dynamic_code_exec(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            self.findings.append(
                Finding(
                    rule_id="SEC-001",
                    title=f"Dynamic Code Execution via `{node.func.id}()`",
                    severity="CRITICAL",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation=f"Avoid using `{node.func.id}()` with dynamic input. Use `ast.literal_eval` or safe parser.",
                )
            )

    def _check_os_and_subprocess(self, node: ast.Call) -> None:
        # os.system / os.popen
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr in ("system", "popen")
        ):
            self.findings.append(
                Finding(
                    rule_id="SEC-002",
                    title=f"Command Injection Risk via `os.{node.func.attr}()`",
                    severity="HIGH",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Use `subprocess.run([...], check=True)` with argument lists instead of shell strings.",
                )
            )

        # subprocess shell=True
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in ("Popen", "run", "call", "check_call", "check_output")
        ):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.findings.append(
                        Finding(
                            rule_id="SEC-006",
                            title="Subprocess invoked with `shell=True`",
                            severity="HIGH",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            snippet=self._get_snippet(node.lineno),
                            recommendation="Pass arguments as a sequence (list) and omit `shell=True` to prevent shell injection.",
                        )
                    )

    def _check_deserialization(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute) or not isinstance(node.func.value, ast.Name):
            return

        # pickle.loads / pickle.load
        if node.func.value.id == "pickle" and node.func.attr in ("loads", "load"):
            self.findings.append(
                Finding(
                    rule_id="SEC-003",
                    title="Insecure Deserialization via `pickle`",
                    severity="HIGH",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Avoid unpickling untrusted data. Use safer serialization formats like JSON or Protocol Buffers.",
                )
            )

        # yaml.load without Loader
        if node.func.value.id in ("yaml", "pyyaml") and node.func.attr == "load":
            has_loader = any(kw.arg in ("Loader", "loader") for kw in node.keywords)
            if not has_loader:
                self.findings.append(
                    Finding(
                        rule_id="SEC-004",
                        title="Arbitrary Code Execution via `yaml.load()` without SafeLoader",
                        severity="HIGH",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_snippet(node.lineno),
                        recommendation="Use `yaml.safe_load(...)` instead of `yaml.load(...)`.",
                    )
                )

    def _check_weak_crypto(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hashlib"
            and node.func.attr in ("md5", "sha1")
        ):
            self.findings.append(
                Finding(
                    rule_id="SEC-005",
                    title=f"Weak Cryptographic Hash Algorithm `{node.func.attr}`",
                    severity="LOW",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Use SHA-256 (`hashlib.sha256()`) or stronger hashing algorithms for security contexts.",
                )
            )

    def _check_sql_injection(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany"):
            if node.args and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp)):
                self.findings.append(
                    Finding(
                        rule_id="SEC-007",
                        title="Potential SQL Injection via Dynamic Query Construction",
                        severity="CRITICAL",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_snippet(node.lineno),
                        recommendation="Use parameterized queries with placeholder bindings (`?` or `%s`), never string interpolation.",
                    )
                )

    def _check_insecure_ssl(self, node: ast.Call) -> None:
        for kw in node.keywords:
            if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                self.findings.append(
                    Finding(
                        rule_id="SEC-008",
                        title="Disabled TLS/SSL Certificate Verification (`verify=False`)",
                        severity="HIGH",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_snippet(node.lineno),
                        recommendation="Do not disable SSL verification in production; it enables Man-In-The-Middle (MITM) attacks.",
                    )
                )

    def _check_tempfile(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "tempfile"
            and node.func.attr == "mktemp"
        ):
            self.findings.append(
                Finding(
                    rule_id="SEC-009",
                    title="Insecure Temporary File Creation via `tempfile.mktemp()`",
                    severity="MEDIUM",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Use `tempfile.NamedTemporaryFile()` or `tempfile.mkstemp()` to prevent race conditions.",
                )
            )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.findings.append(
                Finding(
                    rule_id="CODE-001",
                    title="Bare `except:` Catching SystemExit & KeyboardInterrupt",
                    severity="MEDIUM",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Catch specific exceptions instead of a bare `except:`. At minimum use `except Exception:`.",
                )
            )
        elif (
            isinstance(node.type, ast.Name)
            and node.type.id in ("Exception", "BaseException")
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            self.findings.append(
                Finding(
                    rule_id="CODE-002",
                    title="Silent Exception Suppression (`except Exception: pass`)",
                    severity="LOW",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_snippet(node.lineno),
                    recommendation="Log the exception or handle it explicitly; silencing all exceptions obscures bugs.",
                )
            )
        self.generic_visit(node)


class CodeRuleEngine:
    """Combines AST and regex scanning to detect flaws across a file or repository."""

    SECRET_PATTERNS = [
        (
            re.compile(r"""(?:api_key|apikey|secret|token|password|auth_token)\s*=\s*['"][A-Za-z0-9_\-\.]{16,}['"]""", re.IGNORECASE),
            "SEC-101",
            "Hardcoded Credential / Secret Detected",
            "CRITICAL",
            "Store secrets in environment variables or a secret management vault.",
        ),
        (
            re.compile(r"""(?:::)?AKIA[0-9A-Z]{16}"""),
            "SEC-102",
            "AWS Access Key ID Detected",
            "CRITICAL",
            "Revoke this AWS credential immediately and load credentials from AWS IAM or environment.",
        ),
        (
            re.compile(r"""-----BEGIN (?:RSA|OPENSSH|DSA|EC) PRIVATE KEY-----"""),
            "SEC-103",
            "Private Key Exposed in Code",
            "CRITICAL",
            "Remove private keys from source code and use SSH Agent or key vault.",
        ),
    ]

    @classmethod
    def scan_content(
        cls,
        content: str,
        file_path: str = "<unknown>",
        config: Optional[AgentConfig] = None,
    ) -> List[Finding]:
        cfg = config or AgentConfig()
        lines = content.splitlines()
        findings: List[Finding] = []

        # 1. Regex secrets check
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern, rule_id, title, severity, rec in cls.SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            title=title,
                            severity=cfg.severity_overrides.get(rule_id, severity),
                            file_path=file_path,
                            line_number=lineno,
                            snippet=stripped,
                            recommendation=rec,
                        )
                    )

        # 2. AST security scan
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = SecurityScanner(file_path=file_path, source_lines=lines)
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError as e:
            findings.append(
                Finding(
                    rule_id="SYN-001",
                    title="Syntax Error",
                    severity="HIGH",
                    file_path=file_path,
                    line_number=e.lineno or 1,
                    snippet=lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else "",
                    recommendation=f"Fix syntax error: {e.msg}",
                )
            )

        # 3. Cyclomatic complexity check
        symbols = ASTParser.parse_source(content, filename=file_path)
        threshold = cfg.max_complexity_threshold
        for sym in symbols:
            if sym.complexity >= threshold:
                severity = "HIGH" if sym.complexity >= threshold + 5 else "MEDIUM"
                findings.append(
                    Finding(
                        rule_id="PERF-001",
                        title=f"High Cyclomatic Complexity ({sym.complexity}) in `{sym.name}`",
                        severity=cfg.severity_overrides.get("PERF-001", severity),
                        file_path=file_path,
                        line_number=sym.start_line,
                        snippet=sym.signature or sym.name,
                        recommendation=f"Refactor `{sym.name}` into smaller helper functions to reduce branching logic.",
                    )
                )

        # Filter out disabled rules
        if cfg.disabled_rules:
            disabled = set(cfg.disabled_rules)
            findings = [f for f in findings if f.rule_id not in disabled]

        return findings

    @classmethod
    def scan_file(
        cls,
        path: str | Path,
        config: Optional[AgentConfig] = None,
        cache: Optional[IncrementalCache] = None,
    ) -> List[Finding]:
        file_path = Path(path)
        if not file_path.is_file():
            return []

        if cache:
            cached = cache.get_cached(file_path)
            if cached is not None:
                return cached

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        if file_path.suffix == ".py":
            findings = cls.scan_content(content, file_path=str(file_path), config=config)
        elif MultiLangScanner.is_supported(file_path):
            findings = MultiLangScanner.scan_content(content, file_path=str(file_path))
        else:
            findings = []

        if cache:
            cache.update(file_path, findings)

        return findings

    @classmethod
    def scan_directory(
        cls,
        dir_path: str | Path,
        config: Optional[AgentConfig] = None,
        use_cache: bool = True,
    ) -> List[Finding]:
        root = Path(dir_path)
        if not root.is_dir():
            return []

        cfg = config or AgentConfig.load(root)
        excludes = set(cfg.ignore_paths)
        from .git_tools import GitTools
        cache_root = GitTools.get_repo_root(root) or root
        cache = IncrementalCache(cache_root) if use_cache else None
        findings: List[Finding] = []

        # Find all files
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in excludes for part in p.parts):
                continue
            if p.suffix == ".py" or MultiLangScanner.is_supported(p):
                findings.extend(cls.scan_file(p, config=cfg, cache=cache))

        if cache:
            cache.save()

        return findings
