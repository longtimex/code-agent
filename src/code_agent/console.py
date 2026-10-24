"""Console encoding helpers.

Windows consoles default to a legacy code page (cp1252 on English systems,
cp936 on Chinese ones). The CLI prints Chinese text and emoji throughout, so on
a cp1252 console every ``print()`` raises ``UnicodeEncodeError`` and the tool
dies mid-report. Entry points therefore reconfigure the standard streams to
UTF-8 up-front, with ``errors="replace"`` as a last-resort safety net so a
terminal that still cannot render a glyph degrades to ``?`` instead of crashing.
"""

from __future__ import annotations

import sys


def ensure_utf8_console() -> None:
    """Switches stdout/stderr to UTF-8 when the running interpreter allows it."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # e.g. a StringIO captured by a test runner
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
