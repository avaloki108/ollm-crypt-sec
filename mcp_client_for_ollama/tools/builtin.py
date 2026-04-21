"""Built-in tools for ollmcp -- available without any MCP server.

All tools use the 'builtin.' namespace prefix.
"""
import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import Tool


# ──────────────────────────────────────────────────────────────────
# Tool schemas
# ──────────────────────────────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "name": "Read",
        "description": (
            "Read a file's contents. Line numbers are shown as 'LINE|CONTENT'. "
            "Use offset/limit for large files to avoid reading the whole file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (absolute or relative to CWD)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Starting line number (1-based). Negative counts from end."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "Write",
        "description": (
            "Write content to a file, creating it (and parent dirs) if needed. "
            "Overwrites the entire file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write"
                },
                "contents": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["path", "contents"]
        }
    },
    {
        "name": "Edit",
        "description": (
            "Replace a specific unique string in a file with new content. "
            "old_string MUST appear exactly once. "
            "Use Read first to verify the exact text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact string to find and replace (must be unique in file)"
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement string"
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "Glob",
        "description": (
            "Find files matching a glob pattern. "
            "Patterns without '**/' are prepended with '**/' for recursive search."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "glob_pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.py', '**/*.sol', 'src/**/*.ts')"
                },
                "target_directory": {
                    "type": "string",
                    "description": "Base directory to search (defaults to CWD)"
                }
            },
            "required": ["glob_pattern"]
        }
    },
    {
        "name": "Grep",
        "description": (
            "Search file contents with a regex pattern. "
            "Uses ripgrep (rg) if available, otherwise Python re. "
            "Returns matching lines with file:line:content format."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search (defaults to CWD)"
                },
                "glob": {
                    "type": "string",
                    "description": "Glob filter for files (e.g. '*.py', '*.sol')"
                },
                "-i": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default false)"
                },
                "-C": {
                    "type": "integer",
                    "description": "Lines of context around each match"
                },
                "head_limit": {
                    "type": "integer",
                    "description": "Max results to return (default 100)"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "Shell",
        "description": (
            "Execute a shell command. Returns stdout + stderr. "
            "Commands run in CWD unless working_directory is specified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Directory to run in (defaults to CWD)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "ListDir",
        "description": "List directory contents with type and size metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (defaults to CWD)"
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files (default false)"
                }
            },
            "required": []
        }
    },
    {
        "name": "GitStatus",
        "description": "Show git repository status (staged, unstaged, untracked files).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository or file path (defaults to CWD)"
                }
            },
            "required": []
        }
    },
    {
        "name": "GitDiff",
        "description": "Show git diff for staged or unstaged changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository path or file (defaults to CWD)"
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged diff instead of unstaged (default false)"
                }
            },
            "required": []
        }
    },
    {
        "name": "GitLog",
        "description": "Show recent git commit history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository path (defaults to CWD)"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "name": "GitCommit",
        "description": "Create a git commit. Optionally stages all changes first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "path": {
                    "type": "string",
                    "description": "Repository path (defaults to CWD)"
                },
                "add_all": {
                    "type": "boolean",
                    "description": "Run git add -A before committing (default false)"
                }
            },
            "required": ["message"]
        }
    },
]


def get_builtin_tool_objects() -> List[Tool]:
    """Return mcp.Tool objects for all built-in tools."""
    tools = []
    for schema in _TOOL_SCHEMAS:
        tool = Tool(
            name=f"builtin.{schema['name']}",
            description=f"[builtin] {schema['description']}",
            inputSchema=schema["inputSchema"],
        )
        tools.append(tool)
    return tools


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _resolve(path: Optional[str]) -> Path:
    if not path:
        return Path.cwd()
    p = Path(path).expanduser()
    return p if p.is_absolute() else Path.cwd() / p


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def _git(args: list, cwd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(
            ["git"] + args, capture_output=True, text=True,
            cwd=cwd, timeout=timeout
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode != 0:
            return f"git error (exit {r.returncode}):\n{err or out}"
        return out or "(no output)"
    except FileNotFoundError:
        return "Error: git not found in PATH"
    except subprocess.TimeoutExpired:
        return "Error: git timed out"
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────
# Tool implementations
# ──────────────────────────────────────────────────────────────────

def _read(args: Dict[str, Any]) -> str:
    path = _resolve(args.get("path"))
    offset = args.get("offset")
    limit = args.get("limit")

    if not path.exists():
        return f"Error: File not found: {path}"
    if not path.is_file():
        return f"Error: Not a file: {path}"

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading {path}: {e}"

    lines = raw.splitlines(keepends=True)
    total = len(lines)

    if offset is not None:
        start = (total + offset) if offset < 0 else max(0, offset - 1)
    else:
        start = 0

    end = min(total, start + limit) if limit is not None else total
    selected = lines[start:end]

    numbered = "".join(f"{start + i + 1:6d}|{line}" for i, line in enumerate(selected))
    header = f"File: {path}  ({total} lines"
    if offset is not None or limit is not None:
        header += f", showing {start+1}–{start+len(selected)}"
    return header + ")\n" + numbered


def _write(args: Dict[str, Any]) -> str:
    path = _resolve(args.get("path"))
    contents = args.get("contents", "")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        lines = contents.count("\n") + (1 if contents and not contents.endswith("\n") else 0)
        return f"Wrote {len(contents)} bytes ({lines} lines) to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def _edit(args: Dict[str, Any]) -> str:
    path = _resolve(args.get("path"))
    old_str = args.get("old_string", "")
    new_str = args.get("new_string", "")

    if not path.exists():
        return f"Error: File not found: {path}"

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading {path}: {e}"

    count = content.count(old_str)
    if count == 0:
        return (
            f"Error: old_string not found in {path}.\n"
            "Use Read to inspect the file and verify the exact text."
        )
    if count > 1:
        return f"Error: old_string appears {count} times. Add more context to make it unique."

    try:
        path.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")
    except Exception as e:
        return f"Error writing {path}: {e}"

    return f"Edited {path}: replaced 1 occurrence"


def _glob(args: Dict[str, Any]) -> str:
    pattern = args.get("glob_pattern", "")
    base = _resolve(args.get("target_directory")) if args.get("target_directory") else Path.cwd()

    if not base.exists():
        return f"Error: Directory not found: {base}"

    search = f"**/{pattern}" if not pattern.startswith("**/") else pattern
    try:
        matches = sorted(
            str(p.relative_to(base))
            for p in base.glob(search)
            if p.is_file() or p.is_dir()
        )
    except Exception as e:
        return f"Error: {e}"

    if not matches:
        return f"No files matched '{pattern}' in {base}"

    result = f"Found {len(matches)} result(s) for '{pattern}' in {base}:\n"
    shown = matches[:500]
    result += "\n".join(shown)
    if len(matches) > 500:
        result += f"\n... ({len(matches) - 500} more)"
    return result


def _grep(args: Dict[str, Any]) -> str:
    pattern = args.get("pattern", "")
    path_arg = args.get("path")
    glob_filter = args.get("glob")
    case_insensitive = args.get("-i", False)
    context_lines = args.get("-C", 0)
    max_results = args.get("head_limit", 100)

    search_path = _resolve(path_arg) if path_arg else Path.cwd()

    if shutil.which("rg"):
        cmd = ["rg", "--line-number", "--no-heading"]
        if case_insensitive:
            cmd.append("-i")
        if context_lines:
            cmd += ["-C", str(context_lines)]
        if glob_filter:
            cmd += ["--glob", glob_filter]
        cmd += ["--", pattern, str(search_path)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            out = r.stdout
            if not out:
                return f"No matches found for '{pattern}'"
            lines = out.splitlines()
            if len(lines) > max_results * 2:
                out = "\n".join(lines[: max_results * 2]) + f"\n... (truncated)"
            return out
        except Exception:
            pass  # fall through to Python impl

    # Python fallback
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Invalid regex: {e}"

    results: List[str] = []
    if search_path.is_file():
        files = [search_path]
    else:
        pat = f"**/{glob_filter}" if glob_filter and not glob_filter.startswith("**") else (glob_filter or "**/*")
        files = sorted(p for p in search_path.glob(pat) if p.is_file())

    for fp in files[:300]:
        try:
            file_lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(file_lines, 1):
            if regex.search(line):
                rel = fp.relative_to(search_path) if search_path.is_dir() else fp
                results.append(f"{rel}:{lineno}:{line}")
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    return "\n".join(results) if results else f"No matches found for '{pattern}'"


async def _shell(args: Dict[str, Any]) -> str:
    command = args.get("command", "")
    cwd = str(_resolve(args.get("working_directory"))) if args.get("working_directory") else str(Path.cwd())
    timeout = args.get("timeout", 30)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: command timed out after {timeout}s"

        parts = []
        if stdout:
            parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")
        if proc.returncode not in (0, None):
            parts.append(f"[exit code: {proc.returncode}]")
        return "\n".join(parts) if parts else "(no output)"
    except Exception as e:
        return f"Error: {e}"


def _listdir(args: Dict[str, Any]) -> str:
    path = _resolve(args.get("path"))
    show_hidden = args.get("show_hidden", False)

    if not path.exists():
        return f"Error: Not found: {path}"
    if not path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return f"Error: Permission denied: {path}"

    if not show_hidden:
        entries = [e for e in entries if not e.name.startswith(".")]

    lines = [f"Directory: {path}"]
    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]

    for d in dirs:
        lines.append(f"  [DIR]  {d.name}/")
    for f in files:
        try:
            sz = _fmt_size(f.stat().st_size)
        except Exception:
            sz = "?"
        lines.append(f"  [FILE] {f.name}  ({sz})")

    lines.append(f"\n{len(dirs)} directories, {len(files)} files")
    return "\n".join(lines)


def _git_status(args: Dict[str, Any]) -> str:
    return _git(["status"], str(_resolve(args.get("path"))))


def _git_diff(args: Dict[str, Any]) -> str:
    cwd = str(_resolve(args.get("path")))
    staged = args.get("staged", False)
    diff_args = ["diff", "--cached"] if staged else ["diff"]
    diff = _git(diff_args, cwd)
    if len(diff) > 10000:
        diff = diff[:10000] + "\n... (truncated at 10KB)"
    return diff


def _git_log(args: Dict[str, Any]) -> str:
    cwd = str(_resolve(args.get("path")))
    count = args.get("count", 10)
    return _git(["log", f"--max-count={count}", "--oneline", "--decorate"], cwd)


def _git_commit(args: Dict[str, Any]) -> str:
    cwd = str(_resolve(args.get("path")))
    message = args.get("message", "")
    if not message:
        return "Error: commit message required"
    if args.get("add_all", False):
        _git(["add", "-A"], cwd)
    return _git(["commit", "-m", message], cwd)


# ──────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────

async def execute_builtin_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a built-in tool by name (without 'builtin.' prefix)."""
    try:
        if name == "Read":
            return _read(args)
        elif name == "Write":
            return _write(args)
        elif name == "Edit":
            return _edit(args)
        elif name == "Glob":
            return _glob(args)
        elif name == "Grep":
            return _grep(args)
        elif name == "Shell":
            return await _shell(args)
        elif name == "ListDir":
            return _listdir(args)
        elif name == "GitStatus":
            return _git_status(args)
        elif name == "GitDiff":
            return _git_diff(args)
        elif name == "GitLog":
            return _git_log(args)
        elif name == "GitCommit":
            return _git_commit(args)
        else:
            return f"Error: Unknown built-in tool: {name}"
    except Exception as e:
        return f"Error executing builtin.{name}: {e}"
