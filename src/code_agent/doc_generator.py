"""Automated Project Architecture & API Documentation Generator.

Synthesizes comprehensive ARCHITECTURE.md and API.md documentation directly
from AST symbols, module dependency graphs, and signatures.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from .ast_parser import ASTParser, CodeSymbol
from .call_graph import DependencyGraph
from .config import AgentConfig


class DocGenerator:
    """Generates Markdown architecture topologies and API references."""

    @classmethod
    def generate_api_doc(cls, target_path: Path | str) -> str:
        p = Path(target_path)
        cfg = AgentConfig.load(p if p.is_dir() else p.parent)
        excludes = set(cfg.ignore_paths)

        files = [p] if p.is_file() else [
            f for f in p.rglob("*.py")
            if not any(part in excludes for part in f.parts)
        ]

        lines = [
            "# API 接口参考文档",
            "",
            "> 本文档由 Code Analysis Agent 基于代码 AST 自动生成。",
            "",
        ]

        for f in sorted(files):
            symbols = ASTParser.parse_file(f)
            if not symbols:
                continue

            rel = str(f.name)
            lines.append(f"## 模块 `{rel}`")
            lines.append("")

            # Classes
            classes = [s for s in symbols if s.kind == "class"]
            functions = [s for s in symbols if s.kind in ("function", "async_function")]

            if classes:
                lines.append("### 核心类定义")
                for c in classes:
                    lines.append(f"#### `class {c.name}`")
                    if c.docstring:
                        lines.append(f"> {c.docstring.strip()}\n")
                    lines.append(f"- **定义位置**: 第 {c.start_line} - {c.end_line} 行")

                    methods = [s for s in symbols if s.parent_class == c.name]
                    if methods:
                        lines.append("\n**包含方法**:")
                        for m in methods:
                            lines.append(f"- `{m.signature}`")
                            if m.docstring:
                                lines.append(f"  - *{m.docstring.strip().splitlines()[0]}*")
                    lines.append("")

            if functions:
                lines.append("### 独立函数接口")
                for fn in functions:
                    lines.append(f"#### `{fn.name}`")
                    lines.append(f"```python\n{fn.signature}\n```")
                    if fn.docstring:
                        lines.append(f"{fn.docstring.strip()}\n")
                    lines.append(f"- **复杂度**: {fn.complexity} | **行号**: L{fn.start_line}-L{fn.end_line}")
                    lines.append("")

        return "\n".join(lines)

    @classmethod
    def generate_architecture_doc(cls, root_dir: Path | str) -> str:
        root = Path(root_dir)
        graph = DependencyGraph(root_dir=root)
        data = graph.to_dict()

        lines = [
            f"# 项目架构与模块拓扑指南: {root.name}",
            "",
            "> 本文档由 Code Analysis Agent 自动解析跨文件依赖与符号图生成。",
            "",
            "## 1. 项目概览",
            f"- **源文件总数**: {data['total_files']} 个 Python 模块",
            "",
            "## 2. 模块依赖拓扑图 (Dependency Graph)",
            "",
            "```text",
        ]

        for mod, deps in sorted(data["dependencies"].items()):
            if deps:
                lines.append(f"[{mod}]")
                for d in sorted(deps):
                    lines.append(f"  └──> {d}")

        lines.extend([
            "```",
            "",
            "## 3. 核心调用关系与高内聚模块",
            "",
        ])

        # Top imported modules (most central)
        central_modules = sorted(
            data["dependents"].items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )

        lines.append("| 模块名称 | 被依赖次数 (被调用热度) | 依赖该模块的组件 |")
        lines.append("|---|:---:|---|")
        for mod, callers in central_modules[:10]:
            if callers:
                callers_preview = ", ".join(f"`{c}`" for c in sorted(callers)[:3])
                if len(callers) > 3:
                    callers_preview += f" 等 {len(callers)} 个文件"
                lines.append(f"| `{mod}` | **{len(callers)}** | {callers_preview} |")

        lines.append("")
        return "\n".join(lines)
