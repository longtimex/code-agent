"""Desktop Application Window Launcher.

Launches the local GUI server and opens a dedicated, frameless native desktop
application window.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from typing import Optional

from .gui_server import start_server


def find_free_port(start_port: int = 8765) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def open_desktop_window(url: str) -> None:
    """Attempts to open in frameless application window mode, fallback to default browser."""
    # Check for Edge on Windows
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if os.path.isfile(p):
            subprocess.Popen([p, f"--app={url}"])
            return

    # Check for Chrome on Windows / Linux
    chrome_cmd = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
    if chrome_cmd:
        env = os.environ.copy()
        if "DISPLAY" not in env and os.path.exists("/tmp/.X11-unix/X1"):
            env["DISPLAY"] = ":1"
        subprocess.Popen([chrome_cmd, f"--app={url}", "--window-size=1080,720"], env=env)
        return

    # Fallback to system default browser
    webbrowser.open(url)


def launch_gui(port: Optional[int] = None) -> None:
    selected_port = port or find_free_port()
    server = start_server(port=selected_port)
    url = f"http://127.0.0.1:{selected_port}"

    print(f"\n==================================================================")
    print(f"  🛡️ Code Analysis Agent - 桌面应用程序已启动")
    print(f"  访问地址: {url}")
    print(f"  正在打开本地桌面弹窗应用...")
    print(f"  按 Ctrl+C 关闭程序")
    print(f"==================================================================\n")

    open_desktop_window(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n桌面应用程序已退出。")
        server.shutdown()
