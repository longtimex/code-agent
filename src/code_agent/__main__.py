"""Entry point for both `python -m code_agent` and the PyInstaller build.

The import is absolute on purpose: PyInstaller executes the entry script as a
plain top-level module (`__main__`), where package-relative imports such as
`from .cli import main` cannot be resolved and the bundled exe would fail at
start-up with ModuleNotFoundError.
"""

from code_agent.cli import main

if __name__ == "__main__":
    main()
