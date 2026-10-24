"""GUI entry point used by the PyInstaller build (`build_exe.py --mode gui`).

Same rationale as `__main__.py`: an absolute import keeps the package context
alive when PyInstaller runs this file as a standalone script, so the
`from .xxx import ...` imports inside `gui_app.py` resolve correctly.
"""

from code_agent.gui_app import launch_gui

if __name__ == "__main__":
    launch_gui()
