""" FZF-style command completer for interactive mode using prompt_toolkit.

Supports:
- Fuzzy completion of bare commands (help, model, tools…)
- Slash-prefixed commands (/help, /model, /tools…)
- @file / @dir path completion anywhere in the input
"""
import os
from pathlib import Path

from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter, WordCompleter

from .constants import INTERACTIVE_COMMANDS


# Build the full command word list: bare + slash-prefixed variants
_COMMAND_WORDS = list(INTERACTIVE_COMMANDS.keys()) + [f"/{k}" for k in INTERACTIVE_COMMANDS.keys()]
_COMMAND_DESCRIPTIONS = {**INTERACTIVE_COMMANDS, **{f"/{k}": v for k, v in INTERACTIVE_COMMANDS.items()}}


class FZFStyleCompleter(Completer):
    """Fuzzy completer for interactive commands and @file paths."""

    def __init__(self):
        self._cmd_completer = FuzzyCompleter(
            WordCompleter(_COMMAND_WORDS, ignore_case=True)
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # ── @file / @dir path completion ──────────────────────────────
        # Find the last '@' token in the text
        at_pos = text.rfind('@')
        if at_pos != -1:
            partial = text[at_pos + 1:]
            # Only attempt if partial looks like a path (no spaces after @)
            if ' ' not in partial:
                yield from self._path_completions(partial, at_pos, len(text))
                return

        # ── Command completion (first word only) ─────────────────────
        if ' ' in text:
            return

        for i, completion in enumerate(self._cmd_completer.get_completions(document, complete_event)):
            cmd = completion.text
            description = _COMMAND_DESCRIPTIONS.get(cmd, "")
            display = f"▶ {cmd}" if i == 0 else f"  {cmd}"
            yield Completion(
                cmd,
                start_position=completion.start_position,
                display=display,
                display_meta=description,
            )

    def _path_completions(self, partial: str, at_pos: int, cursor_pos: int):
        """Yield filesystem completions for the partial path after '@'."""
        try:
            p = Path(partial).expanduser() if partial else Path.cwd()

            if partial.endswith('/') or partial.endswith(os.sep):
                directory = p
                prefix = ""
            else:
                directory = p.parent if not p.is_dir() else p
                prefix = p.name if not p.is_dir() else ""

            if not directory.exists():
                return

            # How many chars to replace: length of partial path typed after @
            replace_len = -(len(partial)) if partial else 0

            for entry in sorted(directory.iterdir()):
                # Skip hidden files unless explicitly typed
                if entry.name.startswith('.') and not prefix.startswith('.'):
                    continue
                if not entry.name.lower().startswith(prefix.lower()):
                    continue

                suffix = '/' if entry.is_dir() else ''
                display_text = f"{entry.name}{suffix}"
                full_path = str(entry) + suffix

                # Compute the completion text relative to what was typed after @
                if partial.endswith('/') or partial.endswith(os.sep):
                    completion_text = display_text
                else:
                    completion_text = str(Path(partial).parent / entry.name) + suffix
                    if partial.startswith('./') or partial.startswith('/') or '/' in partial:
                        pass  # keep full relative path
                    else:
                        completion_text = entry.name + suffix

                yield Completion(
                    completion_text,
                    start_position=-len(partial),
                    display=display_text,
                    display_meta="dir" if entry.is_dir() else self._size_str(entry),
                )
        except (PermissionError, OSError):
            return

    @staticmethod
    def _size_str(path: Path) -> str:
        try:
            size = path.stat().st_size
            for unit in ("B", "KB", "MB"):
                if size < 1024:
                    return f"{size:.0f}{unit}"
                size //= 1024
            return f"{size:.0f}GB"
        except OSError:
            return ""
