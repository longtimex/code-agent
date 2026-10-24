"""One-Click Windows .exe Packaging Script using PyInstaller.

Usage:
  python build_exe.py --mode gui    # Build windowed desktop .exe
  python build_exe.py --mode cli    # Build console CLI .exe
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build(mode: str = "gui") -> None:
    print(f"📦 正在准备将 Code Analysis Agent 打包为 Windows .exe 单文件程序 (模式: {mode})...")

    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        print("❌ 未检测到 PyInstaller。请先在终端运行: pip install pyinstaller", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).parent.resolve()
    src_dir = project_root / "src"

    cmd = [
        pyinstaller,
        "--clean",
        "--onefile",
        "--paths", str(src_dir),
    ]

    if mode == "gui":
        cmd.extend([
            "--name", "code-agent-gui",
            "--noconsole",  # Hide terminal black window for pure GUI app
            str(src_dir / "code_agent" / "gui_main.py"),
        ])
    else:
        cmd.extend([
            "--name", "code-agent",
            str(src_dir / "code_agent" / "__main__.py"),
        ])

    print(f"执行命令: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(project_root))
    if res.returncode == 0:
        exe_name = "code-agent-gui.exe" if mode == "gui" else "code-agent.exe"
        output_file = project_root / "dist" / exe_name
        print(f"\n🎉 打包完成！生成的可执行文件位于:\n  {output_file}\n")
    else:
        print(f"\n❌ 打包失败，退出码: {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Code Analysis Agent into a standalone .exe")
    parser.add_argument("--mode", default="gui", choices=["gui", "cli"], help="打包类型: gui (桌面弹窗) 或 cli (命令行)")
    args = parser.parse_args()
    build(mode=args.mode)
