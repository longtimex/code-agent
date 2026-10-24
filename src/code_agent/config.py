"""Project Configuration Management Module.

Supports loading and saving `.code-agent.json` or `.code-agent.yaml` configs
for custom ignore paths, rule severities, and complexity thresholds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentConfig:
    ignore_paths: List[str] = field(
        default_factory=lambda: [
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".pytest_cache",
            ".tox",
        ]
    )
    max_complexity_threshold: int = 10
    disabled_rules: List[str] = field(default_factory=list)
    severity_overrides: Dict[str, str] = field(default_factory=dict)
    default_model: str = "gpt-4o"
    openai_base_url: str = ""
    openai_api_key: str = ""
    max_turns: int = 8
    custom_secret_patterns: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, root_dir: Optional[Path | str] = None) -> "AgentConfig":
        base = Path(root_dir) if root_dir else Path.cwd()
        json_path = base / ".code-agent.json"

        # Check local repo config, then fallback to user home directory ~/.code-agent.json
        candidate_paths = [json_path, Path.home() / ".code-agent.json"]
        for pth in candidate_paths:
            if pth.is_file():
                try:
                    data = json.loads(pth.read_text(encoding="utf-8"))
                    return cls(
                        ignore_paths=data.get("ignore_paths", cls().ignore_paths),
                        max_complexity_threshold=data.get("max_complexity_threshold", 10),
                        disabled_rules=data.get("disabled_rules", []),
                        severity_overrides=data.get("severity_overrides", {}),
                        default_model=data.get("default_model", "gpt-4o"),
                        openai_base_url=data.get("openai_base_url", ""),
                        openai_api_key=data.get("openai_api_key", ""),
                        max_turns=data.get("max_turns", 8),
                        custom_secret_patterns=data.get("custom_secret_patterns", []),
                    )
                except Exception:
                    pass
        return cls()

    def save(self, root_dir: Optional[Path | str] = None) -> Path:
        base = Path(root_dir) if root_dir else Path.cwd()
        target = base / ".code-agent.json"
        content = json.dumps(asdict(self), indent=2, ensure_ascii=False)
        target.write_text(content, encoding="utf-8")
        return target
