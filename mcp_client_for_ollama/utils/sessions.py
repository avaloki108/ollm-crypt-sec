"""Conversation session persistence for ollmcp.

Saves and loads conversation history to/from ~/.config/ollmcp/sessions/.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


SESSIONS_DIR = Path.home() / ".config" / "ollmcp" / "sessions"


def _get_sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def save_session(
    chat_history: List[dict],
    model: str,
    enabled_tools: Optional[Dict[str, bool]] = None,
    system_prompt: str = "",
    name: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    """Save current conversation session to disk.

    Returns:
        Path to the saved file.
    """
    sessions_dir = _get_sessions_dir()
    ts = datetime.now()

    if not name:
        name = ts.strftime("%Y%m%d_%H%M%S")

    # Sanitize: allow alphanumerics, hyphens, underscores
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    session_data = {
        "name": safe_name,
        "timestamp": ts.isoformat(),
        "model": model,
        "cwd": cwd or os.getcwd(),
        "system_prompt": system_prompt,
        "enabled_tools": enabled_tools or {},
        "chat_history": chat_history,
    }

    filepath = sessions_dir / f"{safe_name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    return str(filepath)


def load_session(name: str) -> Optional[dict]:
    """Load a session by name or partial name.

    Returns:
        Session data dict, or None if not found.
    """
    sessions_dir = _get_sessions_dir()

    # Exact match first
    filepath = sessions_dir / f"{name}.json"
    if not filepath.exists():
        # Partial name match, pick most recent
        matches = sorted(sessions_dir.glob(f"*{name}*.json"), key=lambda p: p.stat().st_mtime)
        if not matches:
            return None
        filepath = matches[-1]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_sessions() -> List[dict]:
    """List all saved sessions, most recent first.

    Returns:
        List of dicts with keys: name, timestamp, model, message_count, path
    """
    sessions_dir = _get_sessions_dir()
    sessions = []

    for filepath in sorted(
        sessions_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    ):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "name": data.get("name", filepath.stem),
                "timestamp": data.get("timestamp", ""),
                "model": data.get("model", "?"),
                "message_count": len(data.get("chat_history", [])),
                "path": str(filepath),
            })
        except Exception:
            continue

    return sessions


def delete_session(name: str) -> bool:
    """Delete a session by name. Returns True if deleted."""
    sessions_dir = _get_sessions_dir()
    filepath = sessions_dir / f"{name}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
