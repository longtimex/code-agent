"""AST Parsing and Code Structure Analysis Module.

Provides code symbol extraction, signature detection, cyclomatic complexity
calculation, skeleton/outline generation, and call hierarchy extraction.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CodeSymbol:
    name: str
    kind: str  # 'function', 'async_function', 'class', 'method'
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    signature: str = ""
    decorators: List[str] = field(default_factory=list)
    complexity: int = 1
    calls: List[str] = field(default_factory=list)
    parent_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "parent_class": self.parent_class,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "complexity": self.complexity,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "calls": self.calls,
        }


class ComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe cyclomatic complexity of an AST node."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)


class CallVisitor(ast.NodeVisitor):
    """Collects names of all functions and methods called within a node."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class ASTParser:
    """Parses Python source code and extracts high-level structural semantics."""

    @staticmethod
    def calculate_complexity(node: ast.AST) -> int:
        visitor = ComplexityVisitor()
        visitor.visit(node)
        return visitor.complexity

    @staticmethod
    def extract_calls(node: ast.AST) -> List[str]:
        visitor = CallVisitor()
        visitor.visit(node)
        seen = set()
        unique_calls = []
        for call in visitor.calls:
            if call not in seen:
                seen.add(call)
                unique_calls.append(call)
        return unique_calls

    @staticmethod
    def _format_arg(arg: ast.arg) -> str:
        if not arg.annotation:
            return arg.arg
        try:
            return f"{arg.arg}: {ast.unparse(arg.annotation)}"
        except Exception:
            return f"{arg.arg}: ..."

    @classmethod
    def _format_pos_args(cls, args_list: List[ast.arg], defaults: List[ast.expr]) -> List[str]:
        parts = []
        offset = len(args_list) - len(defaults)
        for i, arg in enumerate(args_list):
            s = cls._format_arg(arg)
            d_idx = i - offset
            if d_idx >= 0:
                try:
                    val = ast.unparse(defaults[d_idx])
                    sep = " = " if ":" in s else "="
                    s = f"{s}{sep}{val}"
                except Exception:
                    s = f"{s}=..."
            parts.append(s)
        return parts

    @classmethod
    def _format_kw_args(cls, kwargs_list: List[ast.arg], kw_defaults: List[Optional[ast.expr]]) -> List[str]:
        parts = []
        for i, arg in enumerate(kwargs_list):
            s = cls._format_arg(arg)
            default_val = kw_defaults[i]
            if default_val is not None:
                try:
                    val = ast.unparse(default_val)
                    sep = " = " if ":" in s else "="
                    s = f"{s}{sep}{val}"
                except Exception:
                    s = f"{s}=..."
            parts.append(s)
        return parts

    @classmethod
    def extract_signature(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        parts: List[str] = []

        # Positional-only args
        posonly = getattr(node.args, "posonlyargs", [])
        if posonly:
            for arg in posonly:
                parts.append(cls._format_arg(arg))
            parts.append("/")

        # Standard positional args
        parts.extend(cls._format_pos_args(node.args.args, node.args.defaults))

        # *vararg
        if node.args.vararg:
            parts.append(f"*{cls._format_arg(node.args.vararg)}")

        # Keyword-only args
        parts.extend(cls._format_kw_args(node.args.kwonlyargs, node.args.kw_defaults))

        # **kwarg
        if node.args.kwarg:
            parts.append(f"**{cls._format_arg(node.args.kwarg)}")

        ret = ""
        if node.returns:
            try:
                ret = f" -> {ast.unparse(node.returns)}"
            except Exception:
                ret = " -> ..."

        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        return f"{prefix}{node.name}({', '.join(parts)}){ret}"

    @classmethod
    def parse_source(cls, code: str, filename: str = "<unknown>") -> List[CodeSymbol]:
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError:
            return []

        symbols: List[CodeSymbol] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(cls._parse_function_symbol(node))
            elif isinstance(node, ast.ClassDef):
                symbols.extend(cls._parse_class_symbols(node))
        return symbols

    @classmethod
    def _parse_function_symbol(
        cls,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_class: Optional[str] = None,
    ) -> CodeSymbol:
        kind = "function"
        if parent_class:
            kind = "async_method" if isinstance(node, ast.AsyncFunctionDef) else "method"
        elif isinstance(node, ast.AsyncFunctionDef):
            kind = "async_function"

        name = f"{parent_class}.{node.name}" if parent_class else node.name
        return CodeSymbol(
            name=name,
            kind=kind,
            parent_class=parent_class,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            signature=cls.extract_signature(node),
            decorators=[ast.unparse(d) for d in node.decorator_list],
            complexity=cls.calculate_complexity(node),
            calls=cls.extract_calls(node),
        )

    @classmethod
    def _parse_class_symbols(cls, node: ast.ClassDef) -> List[CodeSymbol]:
        res = [
            CodeSymbol(
                name=node.name,
                kind="class",
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=ast.get_docstring(node),
                signature=f"class {node.name}",
                decorators=[ast.unparse(d) for d in node.decorator_list],
                complexity=1,
            )
        ]
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                res.append(cls._parse_function_symbol(item, parent_class=node.name))
        return res

    @classmethod
    def parse_file(cls, path: str | Path) -> List[CodeSymbol]:
        file_path = Path(path)
        if not file_path.is_file():
            return []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return cls.parse_source(content, filename=str(file_path))
        except Exception:
            return []

    @classmethod
    def get_skeleton(cls, code: str) -> str:
        """Generates a token-efficient code skeleton (classes, signatures, docstrings)."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return "# [Syntax Error: Unable to parse file]"

        lines: List[str] = []
        mod_doc = ast.get_docstring(tree)
        if mod_doc:
            lines.append(f'"""{mod_doc}"""\n')

        # Top-level imports
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                try:
                    lines.append(ast.unparse(node))
                except Exception:
                    pass

        if lines:
            lines.append("")

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.extend(cls._format_func_skeleton(node))
            elif isinstance(node, ast.ClassDef):
                lines.extend(cls._format_class_skeleton(node))

        return "\n".join(lines).strip()

    @classmethod
    def _format_func_skeleton(cls, node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> List[str]:
        sig = cls.extract_signature(node)
        doc = ast.get_docstring(node)
        res = [f"{indent}{sig}:"]
        if doc:
            res.append(f'{indent}    """{doc}"""')
        res.append(f"{indent}    ...")
        if not indent:
            res.append("")
        return res

    @classmethod
    def _format_class_skeleton(cls, node: ast.ClassDef) -> List[str]:
        bases = ""
        if node.bases:
            try:
                bases = f"({', '.join(ast.unparse(b) for b in node.bases)})"
            except Exception:
                pass
        res = [f"class {node.name}{bases}:"]
        doc = ast.get_docstring(node)
        if doc:
            res.append(f'    """{doc}"""')

        methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not methods:
            res.append("    ...")
        else:
            for m in methods:
                res.extend(cls._format_func_skeleton(m, indent="    "))
        res.append("")
        return res

    @classmethod
    def extract_symbol_source(cls, code: str, symbol_name: str) -> Optional[str]:
        symbols = cls.parse_source(code)
        target = None
        for sym in symbols:
            if sym.name == symbol_name or sym.name.endswith(f".{symbol_name}"):
                target = sym
                break

        if not target:
            return None

        lines = code.splitlines()
        start = max(0, target.start_line - 1)
        end = min(len(lines), target.end_line)
        return "\n".join(lines[start:end])
