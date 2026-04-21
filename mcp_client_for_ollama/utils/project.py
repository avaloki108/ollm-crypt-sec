"""Project-level configuration discovery for ollmcp.

Searches upward from CWD for .ollmcp.yaml and AGENTS.md to provide
project-specific model settings and system prompt additions.
"""
import os
from pathlib import Path
from typing import Optional

import yaml


def _find_project_root(start: Optional[str] = None) -> Optional[Path]:
    """Walk up from start dir looking for .ollmcp.yaml or AGENTS.md.

    Stops at the filesystem root or the user home directory.
    """
    current = Path(start or os.getcwd()).resolve()
    home = Path.home()

    for directory in [current, *current.parents]:
        if (directory / ".ollmcp.yaml").exists() or (directory / "AGENTS.md").exists():
            return directory
        # Stop at home or root to avoid scanning the whole filesystem
        if directory == home or directory == directory.parent:
            break

    return None


def load_project_config(project_dir: Path) -> dict:
    """Load .ollmcp.yaml from project_dir. Returns empty dict if absent."""
    config_file = project_dir / ".ollmcp.yaml"
    if not config_file.exists():
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_agents_md(project_dir: Path) -> str:
    """Load AGENTS.md content from project_dir. Returns empty string if absent."""
    agents_file = project_dir / "AGENTS.md"
    if not agents_file.exists():
        return ""
    try:
        return agents_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def get_project_context(cwd: Optional[str] = None) -> dict:
    """Discover and return project context for the current directory.

    Returns:
        dict with keys:
            project_dir (Path | None): root directory of the project
            system_prompt (str): combined system prompt from AGENTS.md + .ollmcp.yaml
            model (str | None): preferred model from .ollmcp.yaml
            config (dict): raw .ollmcp.yaml contents
    """
    project_dir = _find_project_root(cwd)
    result = {
        "project_dir": project_dir,
        "system_prompt": "",
        "model": None,
        "config": {},
    }

    if project_dir is None:
        return result

    config = load_project_config(project_dir)
    result["config"] = config

    agents_md = load_agents_md(project_dir)

    parts = []
    if agents_md:
        parts.append(f"## Project Instructions (AGENTS.md)\n\n{agents_md.strip()}")
    if config.get("system_prompt"):
        parts.append(str(config["system_prompt"]).strip())

    result["system_prompt"] = "\n\n".join(parts)
    result["model"] = config.get("model")

    return result


def init_project_config(
    cwd: Optional[str] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Path:
    """Create a .ollmcp.yaml in the given directory (or CWD).

    Returns:
        Path to the created config file.
    """
    directory = Path(cwd or os.getcwd())
    config_file = directory / ".ollmcp.yaml"

    config: dict = {}
    if model:
        config["model"] = model
    if system_prompt:
        config["system_prompt"] = system_prompt

    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    return config_file
