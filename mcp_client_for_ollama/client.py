"""MCP Client for Ollama - A TUI client for interacting with Ollama models and MCP servers"""
import asyncio
import datetime
import os
import platform
import re
import subprocess
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import ollama

from . import __version__
from .config.manager import ConfigManager
from .utils.version import check_for_updates
from .utils.constants import (
    DEFAULT_CLAUDE_CONFIG, DEFAULT_MODEL, DEFAULT_OLLAMA_HOST,
    DEFAULT_COMPLETION_STYLE, INTERACTIVE_COMMANDS, SLASH_ALIASES,
)
from .utils.context import trim_messages_for_context
from .utils.sessions import save_session, load_session, list_sessions, delete_session
from .utils.project import get_project_context, init_project_config
from .server.connector import ServerConnector
from .models.manager import ModelManager
from .models.config_manager import ModelConfigManager
from .tools.manager import ToolManager
from .tools.builtin import get_builtin_tool_objects, execute_builtin_tool
from .utils.streaming import StreamingManager
from .utils.tool_display import ToolDisplayManager
from .utils.hil_manager import HumanInTheLoopManager
from .utils.fzf_style_completion import FZFStyleCompleter
from .agents.manager import AgentManager

# Maximum tool-call rounds per user query (agentic loop depth)
MAX_TOOL_ROUNDS = 25


def _clear_screen():
    """Clear the terminal screen safely."""
    if os.name == 'nt':
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)


class MCPClient:
    """Main client class for interacting with Ollama and MCP servers"""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_OLLAMA_HOST,
                 trust_mode: bool = False):
        self.exit_stack = AsyncExitStack()
        self.ollama = ollama.AsyncClient(host=host)
        self.console = Console()
        self.config_manager = ConfigManager(self.console)
        self.server_connector = ServerConnector(self.exit_stack, self.console)
        self.model_manager = ModelManager(console=self.console, default_model=model, ollama=self.ollama)
        self.model_config_manager = ModelConfigManager(console=self.console)
        self.tool_manager = ToolManager(console=self.console, server_connector=self.server_connector)
        self.streaming_manager = StreamingManager(console=self.console)
        self.tool_display_manager = ToolDisplayManager(console=self.console)
        self.hil_manager = HumanInTheLoopManager(console=self.console, trust_mode=trust_mode)
        self.agent_manager = AgentManager(
            console=self.console,
            ollama_client=self.ollama,
            exit_stack=self.exit_stack
        )

        self.sessions = {}
        self.chat_history = []

        history_path = Path.home() / ".config" / "ollmcp" / "command_history"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.prompt_session = PromptSession(
            completer=FZFStyleCompleter(),
            style=Style.from_dict(DEFAULT_COMPLETION_STYLE),
            history=FileHistory(str(history_path)),
        )

        self.retain_context = True
        self.actual_token_count = 0
        self.thinking_mode = True
        self.show_thinking = False
        self.show_tool_execution = True
        self.show_metrics = False
        self.default_configuration_status = False
        self.trust_mode = trust_mode
        self.compact_mode = False
        # Saved display state before compact mode was enabled
        self._pre_compact_state: dict = {}

        self.server_connection_params = {
            'server_paths': None,
            'server_urls': None,
            'config_path': None,
            'auto_discovery': False
        }

        # Project-level context discovered from CWD
        self._project_context: dict = {}
        self._refresh_project_context()

    # ── Project context ─────────────────────────────────────────────

    def _refresh_project_context(self) -> None:
        """(Re)load project config and AGENTS.md from CWD."""
        self._project_context = get_project_context()

    def _build_system_prompt(self) -> str:
        """Combine user system prompt, project context, CWD, OS, date, and tools summary."""
        parts = []

        user_prompt = self.model_config_manager.get_system_prompt()
        if user_prompt:
            parts.append(user_prompt)

        if self._project_context.get("system_prompt"):
            parts.append(self._project_context["system_prompt"])

        cwd = os.getcwd()
        parts.append(f"Current working directory: {cwd}")
        parts.append(f"OS: {platform.system()} {platform.release()}")
        parts.append(f"Date: {datetime.date.today().isoformat()}")

        enabled = self.tool_manager.get_enabled_tool_objects()
        if enabled:
            names = ", ".join(t.name for t in enabled)
            parts.append(f"Available tools ({len(enabled)}): {names}")

        return "\n\n".join(parts)

    # ── Tool setup ──────────────────────────────────────────────────

    def _setup_tools(self, sessions: dict, mcp_tools: list, mcp_enabled: dict) -> None:
        """Combine built-in tools with MCP tools and configure ToolManager."""
        self.sessions = sessions
        builtin_tools = get_builtin_tool_objects()
        all_tools = builtin_tools + mcp_tools
        all_enabled = {bt.name: True for bt in builtin_tools}
        all_enabled.update(mcp_enabled)
        self.tool_manager.set_available_tools(all_tools)
        self.tool_manager.set_enabled_tools(all_enabled)

    def _truncate_tool_result(self, text: str, max_chars: int = 30000) -> str:
        """Truncate long tool results to avoid filling the context window."""
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        omitted = len(text) - max_chars
        return (
            text[:half]
            + f"\n\n... (truncated {omitted:,} characters) ...\n\n"
            + text[-half:]
        )

    # ── Public display helpers ──────────────────────────────────────

    def display_current_model(self):
        self.model_manager.display_current_model()

    async def supports_thinking_mode(self) -> bool:
        try:
            info = await self.ollama.show(self.model_manager.get_current_model())
            return 'thinking' in (info.get('capabilities') or [])
        except Exception:
            return False

    async def select_model(self):
        await self.model_manager.select_model_interactive(clear_console_func=self.clear_console)
        self.display_available_tools()
        self.display_current_model()
        self._display_chat_history()

    def clear_console(self):
        _clear_screen()

    def display_available_tools(self):
        self.tool_manager.display_available_tools()

    # ── Server connection ───────────────────────────────────────────

    async def connect_to_servers(self, server_paths=None, server_urls=None,
                                  config_path=None, auto_discovery=False):
        self.server_connection_params = {
            'server_paths': server_paths,
            'server_urls': server_urls,
            'config_path': config_path,
            'auto_discovery': auto_discovery
        }
        sessions, available_tools, enabled_tools = await self.server_connector.connect_to_servers(
            server_paths=server_paths,
            server_urls=server_urls,
            config_path=config_path,
            auto_discovery=auto_discovery
        )
        self._setup_tools(sessions, available_tools, enabled_tools)

    def select_tools(self):
        self.tool_manager.select_tools(clear_console_func=self.clear_console)
        self.display_available_tools()
        self.display_current_model()
        self._display_chat_history()

    def configure_model_options(self):
        self.model_config_manager.configure_model_interactive(clear_console_func=self.clear_console)
        self.display_available_tools()
        self.display_current_model()
        self._display_chat_history()

    # ── Chat history display ────────────────────────────────────────

    def _display_chat_history(self):
        if not self.chat_history:
            return
        self.console.print(Panel("[bold]Chat History[/bold]", border_style="blue", expand=False))
        max_history = 3
        history_to_show = self.chat_history[-max_history:]
        for i, entry in enumerate(history_to_show):
            q_num = len(self.chat_history) - len(history_to_show) + i + 1
            self.console.print(f"[bold green]Query {q_num}:[/bold green]")
            self.console.print(Text(entry["query"].strip(), style="green"))
            self.console.print("[bold blue]Answer:[/bold blue]")
            self.console.print(Markdown(entry["response"].strip()))
            self.console.print()
        if len(self.chat_history) > max_history:
            self.console.print(
                f"[dim](Showing last {max_history} of {len(self.chat_history)} conversations)[/dim]"
            )

    # ── @file reference expansion ───────────────────────────────────

    def _expand_file_refs(self, query: str) -> tuple:
        """Expand @path references into inline file/directory contents.

        Returns:
            (expanded_query, list_of_included_refs)
        """
        pattern = r'@([\w./\-]+)'
        refs = re.findall(pattern, query)
        if not refs:
            return query, []

        included = []
        context_blocks = []
        for ref in refs:
            p = Path(ref).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    context_blocks.append(f'<file path="{ref}">\n{content}\n</file>')
                    included.append(ref)
                except Exception as e:
                    self.console.print(f"[yellow]Warning: could not read @{ref}: {e}[/yellow]")
            elif p.is_dir():
                entries = sorted(p.iterdir(), key=lambda e: e.name)[:60]
                listing = "\n".join(
                    f"  {'[DIR]' if e.is_dir() else '[FILE]'} {e.name}"
                    for e in entries
                )
                context_blocks.append(f'<directory path="{ref}">\n{listing}\n</directory>')
                included.append(f"{ref}/")
            else:
                self.console.print(f"[yellow]Warning: @{ref} not found, skipping[/yellow]")

        if not context_blocks:
            return query, []

        expanded = "\n\n".join(context_blocks) + "\n\n" + query
        return expanded, included

    # ── Core query processing ───────────────────────────────────────

    async def process_query(self, query: str) -> str:
        """Process a query using Ollama and available tools (agentic loop)."""
        # Expand @file references
        query_expanded, included_refs = self._expand_file_refs(query)
        if included_refs:
            self.console.print(f"[dim]Including: {', '.join(included_refs)}[/dim]")

        # Build initial message list
        current_message = {"role": "user", "content": query_expanded}

        if self.retain_context and self.chat_history:
            messages = []
            for entry in self.chat_history:
                messages.append({"role": "user", "content": entry["query"]})
                messages.append({"role": "assistant", "content": entry["response"]})
            messages.append(current_message)
        else:
            messages = [current_message]

        # Inject combined system prompt (user + project + CWD + OS + date + tools)
        system_prompt = self._build_system_prompt()
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        # Context-window trimming
        num_ctx = self.model_config_manager.get_ollama_options().get("num_ctx", 8192)
        messages, was_trimmed = trim_messages_for_context(messages, max_tokens=num_ctx)
        if was_trimmed:
            self.console.print("[dim]Context trimmed to fit model window.[/dim]")

        enabled_tool_objects = self.tool_manager.get_enabled_tool_objects()
        if not enabled_tool_objects:
            self.console.print(
                "[yellow]Warning: No tools enabled. Model will respond without tool access.[/yellow]"
            )

        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
            }
            for tool in enabled_tool_objects
        ]

        model = self.model_manager.get_current_model()
        model_options = self.model_config_manager.get_ollama_options()
        supports_thinking = await self.supports_thinking_mode()

        # Track tokens generated for this specific query
        query_token_count = 0

        # ── Initial model call ───────────────────────────────────────
        chat_params = {
            "model": model,
            "messages": messages,
            "stream": True,
            "tools": available_tools,
            "options": model_options,
        }
        if supports_thinking:
            chat_params["think"] = self.thinking_mode

        stream = await self.ollama.chat(**chat_params)
        response_text, tool_calls, metrics = await self.streaming_manager.process_streaming_response(
            stream,
            thinking_mode=self.thinking_mode,
            show_thinking=self.show_thinking,
            show_metrics=self.show_metrics,
        )

        if metrics and metrics.get('eval_count'):
            tokens = metrics['eval_count']
            self.actual_token_count += tokens
            query_token_count += tokens

        messages.append({
            "role": "assistant",
            "content": response_text,
            "tool_calls": tool_calls,
        })

        # ── Agentic tool loop ────────────────────────────────────────
        try:
            for tool_round in range(MAX_TOOL_ROUNDS):
                if not tool_calls or not enabled_tool_objects:
                    break

                if tool_round > 0:
                    self.console.print(f"[dim]── Tool round {tool_round + 1} ──[/dim]")

                for tool in tool_calls:
                    tool_name = tool.function.name
                    tool_args = tool.function.arguments

                    # Split server.tool_name -- always feed an error back to model on failure
                    if '.' in tool_name:
                        server_name, actual_tool_name = tool_name.split('.', 1)
                    else:
                        self.console.print(f"[red]Error: Unqualified tool name: {tool_name}[/red]")
                        messages.append({
                            "role": "tool",
                            "content": f"Error: tool name '{tool_name}' must be in 'server.tool_name' format",
                            "tool_name": tool_name,
                        })
                        continue

                    self.tool_display_manager.display_tool_execution(
                        tool_name, tool_args, show=self.show_tool_execution
                    )

                    should_execute = await self.hil_manager.request_tool_confirmation(
                        tool_name, tool_args
                    )

                    if not should_execute:
                        tool_response = "Tool call was skipped by user."
                        self.tool_display_manager.display_tool_response(
                            tool_name, tool_args, tool_response, show=self.show_tool_execution
                        )
                        messages.append({
                            "role": "tool",
                            "content": tool_response,
                            "tool_name": tool_name,
                        })
                        continue

                    # Execute: built-in or MCP
                    if server_name == "builtin":
                        with self.console.status(f"[cyan]⏳ {tool_name}...[/cyan]"):
                            tool_response = await execute_builtin_tool(actual_tool_name, tool_args)
                    else:
                        if server_name not in self.sessions:
                            err = f"Error: unknown server '{server_name}' for tool '{tool_name}'"
                            self.console.print(f"[red]{err}[/red]")
                            messages.append({
                                "role": "tool",
                                "content": err,
                                "tool_name": tool_name,
                            })
                            continue
                        with self.console.status(f"[cyan]⏳ {tool_name}...[/cyan]"):
                            result = await self.sessions[server_name]["session"].call_tool(
                                actual_tool_name, tool_args
                            )
                            tool_response = result.content[0].text if result.content else ""

                    # Truncate large results before storing
                    tool_response = self._truncate_tool_result(tool_response)

                    self.tool_display_manager.display_tool_response(
                        tool_name, tool_args, tool_response, show=self.show_tool_execution
                    )
                    messages.append({
                        "role": "tool",
                        "content": tool_response,
                        "tool_name": tool_name,
                    })

                # Re-call model WITH tools available so it can chain more calls
                followup_params = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "tools": available_tools,
                    "options": model_options,
                }
                if supports_thinking:
                    followup_params["think"] = self.thinking_mode

                stream = await self.ollama.chat(**followup_params)
                response_text, tool_calls, iter_metrics = await self.streaming_manager.process_streaming_response(
                    stream,
                    thinking_mode=self.thinking_mode,
                    show_thinking=self.show_thinking,
                    show_metrics=self.show_metrics,
                )

                if iter_metrics and iter_metrics.get('eval_count'):
                    tokens = iter_metrics['eval_count']
                    self.actual_token_count += tokens
                    query_token_count += tokens

                messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "tool_calls": tool_calls,
                })

                if not tool_calls:
                    break

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Tool loop cancelled.[/yellow]")

        if not response_text:
            self.console.print("[red]No content response received.[/red]")
            response_text = ""

        # Per-query token summary (when metrics enabled)
        if self.show_metrics and query_token_count:
            self.console.print(
                f"[dim]Tokens this query: ~{query_token_count:,}  |  "
                f"Session total: {self.actual_token_count:,}[/dim]"
            )

        # Store original query (not expanded) in history
        self.chat_history.append({"query": query, "response": response_text})
        return response_text

    # ── Input ───────────────────────────────────────────────────────

    async def get_user_input(self, prompt_text: str = None) -> str:
        """Get user input; supports multiline via triple-quote marker."""
        try:
            if prompt_text is None:
                model_name = self.model_manager.get_current_model().split(':')[0]
                tool_count = len(self.tool_manager.get_enabled_tool_objects())

                # Compact CWD display
                cwd = os.getcwd()
                home = str(Path.home())
                if cwd.startswith(home):
                    cwd_display = "~" + cwd[len(home):]
                else:
                    cwd_display = cwd
                parts = Path(cwd_display).parts
                if len(parts) > 3:
                    cwd_display = "…/" + "/".join(parts[-2:])

                prompt_text = model_name
                if self.thinking_mode and await self.supports_thinking_mode():
                    prompt_text += "/thinking" if not self.show_thinking else "/show-thinking"
                if tool_count > 0:
                    prompt_text += f"/{tool_count}-tools"
                prompt_text += f" {cwd_display}"

            line = await self.prompt_session.prompt_async(f"{prompt_text}❯ ")

            # Multiline mode triggered by triple-quote on its own
            stripped = line.strip()
            if stripped in ('"""', "'''"):
                marker = stripped
                self.console.print(
                    f"[dim]Multiline mode. Type {marker} alone on a new line to submit.[/dim]"
                )
                collected = []
                while True:
                    try:
                        next_line = await self.prompt_session.prompt_async("... ")
                        if next_line.strip() == marker:
                            break
                        collected.append(next_line)
                    except (KeyboardInterrupt, EOFError):
                        break
                return "\n".join(collected)

            return line

        except KeyboardInterrupt:
            return "quit"
        except EOFError:
            return "quit"

    # ── Update check ────────────────────────────────────────────────

    async def display_check_for_updates(self):
        try:
            update_available, current_version, latest_version = check_for_updates()
            if update_available:
                self.console.print(Panel(
                    f"[bold yellow]New version available![/bold yellow]\n\n"
                    f"Current: [cyan]{current_version}[/cyan]  →  Latest: [green]{latest_version}[/green]\n\n"
                    f"Upgrade: [bold white]pip install --upgrade mcp-client-for-ollama[/bold white]",
                    title="Update Available", border_style="yellow", expand=False
                ))
        except Exception:
            pass

    # ── Main chat loop ──────────────────────────────────────────────

    async def chat_loop(self):
        """Run an interactive chat loop."""
        _clear_screen()
        self.console.print(Panel(
            Text.from_markup("[bold green]Welcome to the MCP Client for Ollama 🦙[/bold green]", justify="center"),
            expand=True, border_style="green"
        ))
        self.display_available_tools()
        self.display_current_model()
        self.print_help()
        self.print_auto_load_default_config_status()
        await self.display_check_for_updates()

        if self._project_context.get("project_dir"):
            self.console.print(
                f"[dim]Project config: {self._project_context['project_dir']}[/dim]"
            )

        while True:
            try:
                query = await self.get_user_input()

                # Normalise slash commands (/help → help)
                normalized = query.strip()
                if normalized.startswith('/'):
                    bare = normalized[1:].lower()
                    if bare in INTERACTIVE_COMMANDS:
                        normalized = bare

                cmd = normalized.lower().strip()

                if cmd in ('quit', 'q', 'exit', 'bye'):
                    self.console.print("[yellow]Exiting...[/yellow]")
                    break

                if cmd in ('tools', 't'):
                    self.select_tools()
                    continue

                if cmd in ('help', 'h'):
                    self.print_help()
                    continue

                if cmd in ('model', 'm'):
                    await self.select_model()
                    continue

                if cmd in ('model-config', 'mc'):
                    self.configure_model_options()
                    continue

                if cmd in ('context', 'c'):
                    self.toggle_context_retention()
                    continue

                if cmd in ('thinking-mode', 'tm'):
                    await self.toggle_thinking_mode()
                    continue

                if cmd in ('show-thinking', 'st'):
                    await self.toggle_show_thinking()
                    continue

                if cmd in ('show-tool-execution', 'ste'):
                    self.toggle_show_tool_execution()
                    continue

                if cmd in ('show-metrics', 'sm'):
                    self.toggle_show_metrics()
                    continue

                if cmd in ('clear', 'cc'):
                    self.clear_context()
                    continue

                if cmd in ('context-info', 'ci'):
                    self.display_context_stats()
                    continue

                if cmd in ('cls', 'clear-screen'):
                    _clear_screen()
                    self.display_available_tools()
                    self.display_current_model()
                    continue

                if cmd in ('save-config', 'sc'):
                    config_name = await self.get_user_input("Config name (Enter = default)")
                    config_name = config_name.strip() or "default"
                    self.save_configuration(config_name)
                    continue

                if cmd in ('load-config', 'lc'):
                    config_name = await self.get_user_input("Config name to load (Enter = default)")
                    config_name = config_name.strip() or "default"
                    self.load_configuration(config_name)
                    self.display_available_tools()
                    self.display_current_model()
                    continue

                if cmd in ('reset-config', 'rc'):
                    self.reset_configuration()
                    self.display_available_tools()
                    self.display_current_model()
                    continue

                if cmd in ('reload-servers', 'rs'):
                    await self.reload_servers()
                    continue

                if cmd in ('agent', 'ag'):
                    await self.agent_menu()
                    continue

                if cmd in ('list-agents', 'la'):
                    self.agent_manager.display_agents()
                    continue

                if cmd in ('human-in-the-loop', 'hil'):
                    self.hil_manager.toggle()
                    continue

                # ── Compact mode ──────────────────────────────────
                if cmd in ('compact',):
                    self.toggle_compact_mode()
                    continue

                # ── Session commands ──────────────────────────────
                if cmd in ('sessions', 'ss'):
                    self._display_sessions()
                    continue

                if cmd == 'save-session':
                    name = await self.get_user_input("Session name (Enter = timestamp)")
                    name = name.strip() or None
                    path = save_session(
                        chat_history=self.chat_history,
                        model=self.model_manager.get_current_model(),
                        enabled_tools=self.tool_manager.get_enabled_tools(),
                        system_prompt=self.model_config_manager.get_system_prompt() or "",
                        name=name,
                    )
                    self.console.print(f"[green]Session saved: {path}[/green]")
                    continue

                if cmd == 'load-session':
                    self._display_sessions()
                    name = await self.get_user_input("Session name to load")
                    name = name.strip()
                    if not name:
                        continue
                    data = load_session(name)
                    if data is None:
                        self.console.print(f"[red]Session '{name}' not found.[/red]")
                    else:
                        self.chat_history = data.get("chat_history", [])
                        # Restore model
                        if data.get("model"):
                            self.model_manager.set_model(data["model"])
                        # Restore enabled tools
                        if data.get("enabled_tools"):
                            available = {t.name for t in self.tool_manager.get_available_tools()}
                            for tool_name, enabled in data["enabled_tools"].items():
                                if tool_name in available:
                                    self.tool_manager.set_tool_status(tool_name, enabled)
                        # Restore system prompt
                        if data.get("system_prompt"):
                            self.model_config_manager.system_prompt = data["system_prompt"]
                        self.console.print(
                            f"[green]Loaded session '{data['name']}' "
                            f"({len(self.chat_history)} messages, "
                            f"model: {data.get('model','?')})[/green]"
                        )
                    continue

                if cmd == 'delete-session':
                    self._display_sessions()
                    name = await self.get_user_input("Session name to delete")
                    name = name.strip()
                    if not name:
                        continue
                    if delete_session(name):
                        self.console.print(f"[green]Session '{name}' deleted.[/green]")
                    else:
                        self.console.print(f"[red]Session '{name}' not found.[/red]")
                    continue

                # ── Project commands ──────────────────────────────
                if cmd == 'init':
                    model_input = await self.get_user_input(
                        f"Default model (Enter = {self.model_manager.get_current_model()})"
                    )
                    chosen_model = model_input.strip() or self.model_manager.get_current_model()
                    cfg_path = init_project_config(model=chosen_model)
                    self.console.print(f"[green]Created: {cfg_path}[/green]")
                    self._refresh_project_context()
                    continue

                if cmd == 'git':
                    from .tools.builtin import _git
                    status = _git(["status"], os.getcwd())
                    self.console.print(Panel(status, title="git status", border_style="cyan", expand=False))
                    continue

                # Skip empty input
                if not query.strip():
                    continue

                try:
                    await self.process_query(query)
                except ollama.ResponseError as e:
                    error_msg = str(e)
                    if "does not support tools" in error_msg.lower():
                        model_name = self.model_manager.get_current_model()
                        self.console.print(Panel(
                            f"[bold red]Model Error:[/bold red] "
                            f"[bold blue]{model_name}[/bold blue] does not support tools.\n\n"
                            "Switch model: [bold cyan]model[/bold cyan]  "
                            "or disable tools: [bold cyan]tools[/bold cyan]",
                            title="Tools Not Supported", border_style="red", expand=False
                        ))
                    elif "not found" in error_msg.lower():
                        model_name = self.model_manager.get_current_model()
                        self.console.print(Panel(
                            f"[bold yellow]Model not found.[/bold yellow]\n\n"
                            f"Run: [bold cyan]ollama pull {model_name}[/bold cyan]",
                            title="Model Not Available", border_style="yellow", expand=False
                        ))
                    else:
                        self.console.print(Panel(
                            f"[bold red]Ollama Error:[/bold red] {error_msg}",
                            border_style="red", expand=False
                        ))

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Cancelled.[/yellow]")
                continue

            except Exception as e:
                self.console.print(Panel(
                    f"[bold red]Error:[/bold red] {str(e)}",
                    title="Exception", border_style="red", expand=False
                ))
                self.console.print_exception()

    # ── Session display ─────────────────────────────────────────────

    def _display_sessions(self):
        sessions = list_sessions()
        if not sessions:
            self.console.print("[yellow]No saved sessions found.[/yellow]")
            return
        table = Table(title="Saved Sessions", border_style="cyan")
        table.add_column("Name", style="bold cyan")
        table.add_column("Timestamp")
        table.add_column("Model")
        table.add_column("Messages", justify="right")
        for s in sessions:
            table.add_row(
                s["name"],
                s["timestamp"][:19].replace("T", " "),
                s["model"],
                str(s["message_count"]),
            )
        self.console.print(table)

    # ── Help ────────────────────────────────────────────────────────

    def print_help(self):
        self.console.print(Panel(
            "[bold yellow]Available Commands[/bold yellow] "
            "[dim](/ prefix optional: /help or help)[/dim]\n\n"

            "[bold cyan]Model:[/bold cyan]\n"
            "  [bold]model[/bold]/[bold]m[/bold]              Select model\n"
            "  [bold]model-config[/bold]/[bold]mc[/bold]      Configure system prompt & params\n"
            "  [bold]thinking-mode[/bold]/[bold]tm[/bold]     Toggle thinking mode\n"
            "  [bold]show-thinking[/bold]/[bold]st[/bold]     Toggle thinking visibility\n"
            "  [bold]show-metrics[/bold]/[bold]sm[/bold]      Toggle performance metrics\n\n"

            "[bold cyan]Tools & Servers:[/bold cyan]\n"
            "  [bold]tools[/bold]/[bold]t[/bold]              Configure tools\n"
            "  [bold]show-tool-execution[/bold]/[bold]ste[/bold]  Toggle tool display\n"
            "  [bold]human-in-the-loop[/bold]/[bold]hil[/bold]   Toggle HIL confirmations\n"
            "  [bold]reload-servers[/bold]/[bold]rs[/bold]    Reload MCP servers\n\n"

            "[bold cyan]Context:[/bold cyan]\n"
            "  [bold]context[/bold]/[bold]c[/bold]            Toggle context retention\n"
            "  [bold]clear[/bold]/[bold]cc[/bold]             Clear conversation\n"
            "  [bold]context-info[/bold]/[bold]ci[/bold]      Show context stats\n\n"

            "[bold cyan]Sessions:[/bold cyan]\n"
            "  [bold]sessions[/bold]/[bold]ss[/bold]          List saved sessions\n"
            "  [bold]save-session[/bold]              Save current conversation\n"
            "  [bold]load-session[/bold]              Load a saved conversation\n"
            "  [bold]delete-session[/bold]            Delete a saved conversation\n\n"

            "[bold cyan]Project:[/bold cyan]\n"
            "  [bold]init[/bold]                      Create .ollmcp.yaml in CWD\n"
            "  [bold]git[/bold]                       Show git status\n\n"

            "[bold cyan]Configuration:[/bold cyan]\n"
            "  [bold]save-config[/bold]/[bold]sc[/bold]       Save configuration\n"
            "  [bold]load-config[/bold]/[bold]lc[/bold]       Load configuration\n"
            "  [bold]reset-config[/bold]/[bold]rc[/bold]      Reset to defaults\n\n"

            "[bold cyan]Agents:[/bold cyan]\n"
            "  [bold]agent[/bold]/[bold]ag[/bold]             Manage specialized agents\n"
            "  [bold]list-agents[/bold]/[bold]la[/bold]       List agents\n\n"

            "[bold cyan]Input:[/bold cyan]\n"
            '  Type [bold]"""[/bold] to enter multiline input mode\n'
            "  Use [bold]@path/to/file[/bold] in queries to include file contents\n\n"

            "[bold cyan]UI:[/bold cyan]\n"
            "  [bold]compact[/bold]                   Toggle compact output mode\n"
            "  [bold]clear-screen[/bold]/[bold]cls[/bold]     Clear screen\n"
            "  [bold]help[/bold]/[bold]h[/bold]               Show this help\n"
            "  [bold]quit[/bold]/[bold]q[/bold] / Ctrl+D      Exit\n",
            title="[bold]Help[/bold]", border_style="yellow", expand=False
        ))

    # ── Toggles ─────────────────────────────────────────────────────

    def toggle_context_retention(self):
        self.retain_context = not self.retain_context
        self.console.print(
            f"[green]Context retention {'enabled' if self.retain_context else 'disabled'}![/green]"
        )
        self.display_context_stats()

    async def toggle_thinking_mode(self):
        if not await self.supports_thinking_mode():
            self.console.print(Panel(
                f"[bold red]Thinking mode not supported for "
                f"'{self.model_manager.get_current_model().split(':')[0]}'[/bold red]\n\n"
                "Use [bold cyan]model[/bold cyan] to switch to a supported model.",
                title="Thinking Mode Unavailable", border_style="red", expand=False
            ))
            return
        self.thinking_mode = not self.thinking_mode
        self.console.print(f"[green]Thinking mode {'enabled' if self.thinking_mode else 'disabled'}![/green]")

    async def toggle_show_thinking(self):
        if not self.thinking_mode:
            self.console.print("[yellow]Enable thinking-mode first.[/yellow]")
            return
        self.show_thinking = not self.show_thinking
        self.console.print(
            f"[green]Thinking text {'visible' if self.show_thinking else 'hidden'}![/green]"
        )

    def toggle_show_tool_execution(self):
        self.show_tool_execution = not self.show_tool_execution
        self.console.print(
            f"[green]Tool execution display {'enabled' if self.show_tool_execution else 'disabled'}![/green]"
        )

    def toggle_show_metrics(self):
        self.show_metrics = not self.show_metrics
        self.console.print(
            f"[green]Performance metrics {'enabled' if self.show_metrics else 'disabled'}![/green]"
        )

    def toggle_compact_mode(self):
        """Toggle compact output mode -- hides tool display, metrics, and thinking at once."""
        if not self.compact_mode:
            # Save current state before enabling compact
            self._pre_compact_state = {
                "show_tool_execution": self.show_tool_execution,
                "show_metrics": self.show_metrics,
                "show_thinking": self.show_thinking,
            }
            self.compact_mode = True
            self.show_tool_execution = False
            self.show_metrics = False
            self.show_thinking = False
            self.console.print("[green]Compact mode enabled.[/green]")
            self.console.print("[dim]Tool display, metrics, and thinking hidden.[/dim]")
        else:
            # Restore saved state
            self.compact_mode = False
            self.show_tool_execution = self._pre_compact_state.get("show_tool_execution", True)
            self.show_metrics = self._pre_compact_state.get("show_metrics", False)
            self.show_thinking = self._pre_compact_state.get("show_thinking", False)
            self.console.print("[green]Compact mode disabled. Previous display settings restored.[/green]")

    def clear_context(self):
        count = len(self.chat_history)
        self.chat_history = []
        self.actual_token_count = 0
        self.console.print(f"[green]Context cleared ({count} entries removed).[/green]")

    def display_context_stats(self):
        proj = self._project_context.get('project_dir')
        self.console.print(Panel(
            f"Context retention:   [{'green' if self.retain_context else 'red'}]{'On' if self.retain_context else 'Off'}[/]\n"
            f"Thinking mode:       [{'green' if self.thinking_mode else 'red'}]{'On' if self.thinking_mode else 'Off'}[/]\n"
            f"Show thinking:       [{'green' if self.show_thinking else 'red'}]{'On' if self.show_thinking else 'Off'}[/]\n"
            f"Tool display:        [{'green' if self.show_tool_execution else 'red'}]{'On' if self.show_tool_execution else 'Off'}[/]\n"
            f"Metrics display:     [{'green' if self.show_metrics else 'red'}]{'On' if self.show_metrics else 'Off'}[/]\n"
            f"Compact mode:        [{'yellow' if self.compact_mode else 'dim'}]{'On' if self.compact_mode else 'Off'}[/]\n"
            f"HIL confirmations:   [{'green' if self.hil_manager.is_enabled() else 'red'}]{'On' if self.hil_manager.is_enabled() else 'Off'}[/]\n"
            f"Trust mode:          [{'yellow' if self.trust_mode else 'dim'}]{'On' if self.trust_mode else 'Off'}[/]\n"
            f"Conversation turns:  {len(self.chat_history)}\n"
            f"Tokens generated:    {self.actual_token_count:,}\n"
            f"Project dir:         {proj or '[dim]none[/dim]'}",
            title="Context Info", border_style="cyan", expand=False
        ))

    # ── Configuration ───────────────────────────────────────────────

    def auto_load_default_config(self):
        if self.config_manager.config_exists("default"):
            self.default_configuration_status = self.load_configuration("default")

    def print_auto_load_default_config_status(self):
        if self.default_configuration_status:
            self.console.print("[green] ✓ Default configuration loaded successfully![/green]")
            self.console.print()

    def save_configuration(self, config_name=None):
        config_data = {
            "model": self.model_manager.get_current_model(),
            "enabledTools": self.tool_manager.get_enabled_tools(),
            "contextSettings": {"retainContext": self.retain_context},
            "modelSettings": {
                "thinkingMode": self.thinking_mode,
                "showThinking": self.show_thinking,
            },
            "modelConfig": self.model_config_manager.get_config(),
            "displaySettings": {
                "showToolExecution": self.show_tool_execution,
                "showMetrics": self.show_metrics,
            },
            "hilSettings": {"enabled": self.hil_manager.is_enabled()},
        }
        return self.config_manager.save_configuration(config_data, config_name)

    def load_configuration(self, config_name=None):
        config_data = self.config_manager.load_configuration(config_name)
        if not config_data:
            return False

        if "model" in config_data:
            self.model_manager.set_model(config_data["model"])

        if "enabledTools" in config_data:
            available = {t.name for t in self.tool_manager.get_available_tools()}
            for tool_name, enabled in config_data["enabledTools"].items():
                if tool_name in available:
                    self.tool_manager.set_tool_status(tool_name, enabled)
                    if not tool_name.startswith("builtin."):
                        self.server_connector.set_tool_status(tool_name, enabled)

        if "contextSettings" in config_data:
            self.retain_context = config_data["contextSettings"].get("retainContext", self.retain_context)

        if "modelSettings" in config_data:
            self.thinking_mode = config_data["modelSettings"].get("thinkingMode", self.thinking_mode)
            self.show_thinking = config_data["modelSettings"].get("showThinking", self.show_thinking)

        if "modelConfig" in config_data:
            self.model_config_manager.set_config(config_data["modelConfig"])

        if "displaySettings" in config_data:
            self.show_tool_execution = config_data["displaySettings"].get(
                "showToolExecution", self.show_tool_execution
            )
            self.show_metrics = config_data["displaySettings"].get("showMetrics", self.show_metrics)

        if "hilSettings" in config_data:
            self.hil_manager.set_enabled(config_data["hilSettings"].get("enabled", True))

        return True

    def reset_configuration(self):
        config_data = self.config_manager.reset_configuration()
        self.tool_manager.enable_all_tools()
        self.server_connector.enable_all_tools()

        cs = config_data.get("contextSettings", {})
        self.retain_context = cs.get("retainContext", True)

        ms = config_data.get("modelSettings", {})
        self.thinking_mode = ms.get("thinkingMode", False)
        self.show_thinking = ms.get("showThinking", True)

        ds = config_data.get("displaySettings", {})
        self.show_tool_execution = ds.get("showToolExecution", True)
        self.show_metrics = ds.get("showMetrics", False)

        hs = config_data.get("hilSettings", {})
        self.hil_manager.set_enabled(hs.get("enabled", True))

        return True

    # ── Server reload ───────────────────────────────────────────────

    async def reload_servers(self):
        if not any(self.server_connection_params.values()):
            self.console.print("[yellow]No server parameters stored. Cannot reload.[/yellow]")
            return

        self.console.print("[cyan]🔄 Reloading MCP servers...[/cyan]")
        try:
            current_enabled = self.tool_manager.get_enabled_tools().copy()
            await self.server_connector.disconnect_all_servers()
            self.exit_stack = self.server_connector.exit_stack

            await self.connect_to_servers(
                server_paths=self.server_connection_params['server_paths'],
                server_urls=self.server_connection_params['server_urls'],
                config_path=self.server_connection_params['config_path'],
                auto_discovery=self.server_connection_params['auto_discovery'],
            )

            available = {t.name for t in self.tool_manager.get_available_tools()}
            for tool_name, enabled in current_enabled.items():
                if tool_name in available:
                    self.tool_manager.set_tool_status(tool_name, enabled)
                    if not tool_name.startswith("builtin."):
                        self.server_connector.set_tool_status(tool_name, enabled)

            self.console.print("[green]✅ MCP servers reloaded successfully![/green]")
            self.display_available_tools()

        except Exception as e:
            self.console.print(Panel(
                f"[bold red]Reload failed:[/bold red] {str(e)}",
                title="Reload Failed", border_style="red", expand=False
            ))

    # ── Agent menu ──────────────────────────────────────────────────

    async def agent_menu(self):
        from rich.prompt import Prompt
        while True:
            _clear_screen()
            self.console.print(Panel(
                "[bold yellow]Agent Management Menu[/bold yellow]\n\n"
                "1. Create a new agent\n"
                "2. List all agents\n"
                "3. Execute task with agent\n"
                "4. Load agent from config file\n"
                "5. Remove an agent\n"
                "6. Show agent details\n"
                "7. Back to main menu",
                title="Specialized Agents", border_style="cyan"
            ))
            choice = Prompt.ask(
                "[bold]Select action[/bold]",
                choices=["1", "2", "3", "4", "5", "6", "7"],
                default="7"
            )
            if choice == "1":
                await self.create_agent_interactive()
            elif choice == "2":
                self.agent_manager.display_agents()
                await self.get_user_input("Press Enter to continue")
            elif choice == "3":
                await self.execute_agent_task_interactive()
            elif choice == "4":
                await self.load_agent_from_config_interactive()
            elif choice == "5":
                await self.remove_agent_interactive()
            elif choice == "6":
                await self.show_agent_details_interactive()
            elif choice == "7":
                break

    async def create_agent_interactive(self):
        from rich.prompt import Prompt
        self.console.print(Panel("[bold]Create New Agent[/bold]", border_style="green"))
        agent_type = Prompt.ask("Agent type", choices=["web3_audit", "base"], default="web3_audit")
        name = Prompt.ask("Agent name", default=f"{agent_type}-agent")
        model = Prompt.ask("Model", default="qwen2.5:7b")
        config = {}
        if agent_type == "base":
            config = {
                "description": Prompt.ask("Description"),
                "system_prompt": Prompt.ask("System prompt"),
            }
        agent = self.agent_manager.create_agent(agent_type, name, model, config)
        if agent:
            connect = Prompt.ask("Connect to MCP servers?", choices=["yes", "no"], default="no")
            if connect == "yes":
                server_choice = Prompt.ask(
                    "1 = same as main, 2 = custom", choices=["1", "2"], default="1"
                )
                if server_choice == "1":
                    await agent.connect_to_servers(
                        server_paths=self.server_connection_params.get('server_paths'),
                        server_urls=self.server_connection_params.get('server_urls'),
                        config_path=self.server_connection_params.get('config_path'),
                    )
                else:
                    cfg = Prompt.ask("Server config path")
                    if cfg.strip():
                        await agent.connect_to_servers(config_path=cfg)
        await self.get_user_input("Press Enter to continue")

    async def execute_agent_task_interactive(self):
        from rich.prompt import Prompt
        agents = self.agent_manager.list_agents()
        if not agents:
            self.console.print("[yellow]No agents. Create one first.[/yellow]")
            await self.get_user_input("Press Enter to continue")
            return
        self.agent_manager.display_agents()
        agent_name = Prompt.ask("Agent name", choices=agents, default=agents[0])
        task = Prompt.ask("Task description")
        await self.agent_manager.execute_agent_task(agent_name, task)
        await self.get_user_input("Press Enter to continue")

    async def load_agent_from_config_interactive(self):
        from rich.prompt import Prompt
        self.console.print(Panel(
            "[bold]Load Agent from Config[/bold]\n\nYAML or JSON. See config/agents/",
            border_style="cyan"
        ))
        cfg = Prompt.ask("Config file path")
        if cfg.strip():
            await self.agent_manager.create_agent_from_config(cfg)
        await self.get_user_input("Press Enter to continue")

    async def remove_agent_interactive(self):
        from rich.prompt import Prompt
        agents = self.agent_manager.list_agents()
        if not agents:
            self.console.print("[yellow]No agents to remove.[/yellow]")
            await self.get_user_input("Press Enter to continue")
            return
        self.agent_manager.display_agents()
        agent_name = Prompt.ask("Agent to remove", choices=agents + ["cancel"], default="cancel")
        if agent_name != "cancel":
            self.agent_manager.remove_agent(agent_name)
        await self.get_user_input("Press Enter to continue")

    async def show_agent_details_interactive(self):
        import json
        from rich.prompt import Prompt
        agents = self.agent_manager.list_agents()
        if not agents:
            self.console.print("[yellow]No agents.[/yellow]")
            await self.get_user_input("Press Enter to continue")
            return
        self.agent_manager.display_agents()
        agent_name = Prompt.ask("Agent name", choices=agents, default=agents[0])
        agent = self.agent_manager.get_agent(agent_name)
        if agent:
            self.console.print(Panel(
                json.dumps(agent.get_info(), indent=2),
                title=f"Agent: {agent_name}", border_style="cyan"
            ))
        await self.get_user_input("Press Enter to continue")

    # ── Cleanup ─────────────────────────────────────────────────────

    async def cleanup(self):
        await self.agent_manager.cleanup_all()
        await self.exit_stack.aclose()


# ── CLI ──────────────────────────────────────────────────────────────

app = typer.Typer(
    help="MCP Client for Ollama",
    context_settings={"help_option_names": ["-h", "--help"]}
)


@app.command()
def main(
    mcp_server: Optional[List[str]] = typer.Option(
        None, "--mcp-server", "-s",
        help="Path to a server script (.py or .js)",
        rich_help_panel="MCP Server Configuration"
    ),
    mcp_server_url: Optional[List[str]] = typer.Option(
        None, "--mcp-server-url", "-u",
        help="URL for SSE or Streamable HTTP MCP server",
        rich_help_panel="MCP Server Configuration"
    ),
    servers_json: Optional[str] = typer.Option(
        None, "--servers-json", "-j",
        help="Path to JSON file with server configurations",
        rich_help_panel="MCP Server Configuration"
    ),
    auto_discovery: bool = typer.Option(
        False, "--auto-discovery", "-a",
        help=f"Auto-discover servers from Claude's config at {DEFAULT_CLAUDE_CONFIG}",
        rich_help_panel="MCP Server Configuration"
    ),
    model: str = typer.Option(
        DEFAULT_MODEL, "--model", "-m",
        help="Ollama model to use",
        rich_help_panel="Ollama Configuration"
    ),
    host: str = typer.Option(
        DEFAULT_OLLAMA_HOST, "--host", "-H",
        help="Ollama host URL",
        rich_help_panel="Ollama Configuration"
    ),
    trust: bool = typer.Option(
        False, "--trust",
        help="Trust mode: auto-approve all tool calls (no HIL prompts)",
        rich_help_panel="Permissions"
    ),
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        help="Show version and exit",
    ),
):
    """Run the MCP Client for Ollama."""
    if version:
        typer.echo(f"mcp-client-for-ollama {__version__}")
        raise typer.Exit()

    if not (mcp_server or mcp_server_url or servers_json or auto_discovery):
        auto_discovery = True

    asyncio.run(async_main(mcp_server, mcp_server_url, servers_json, auto_discovery, model, host, trust))


async def async_main(mcp_server, mcp_server_url, servers_json, auto_discovery, model, host, trust=False):
    """Asynchronous entry point."""
    console = Console()
    client = MCPClient(model=model, host=host, trust_mode=trust)

    if not await client.model_manager.check_ollama_running():
        console.print(Panel(
            "[bold red]Error: Ollama is not running![/bold red]\n\n"
            "Start it with: [bold cyan]ollama serve[/bold cyan]",
            title="Ollama Not Running", border_style="red", expand=False
        ))
        return

    config_path = None
    auto_discovery_final = auto_discovery

    if servers_json:
        if os.path.exists(servers_json):
            config_path = servers_json
        else:
            console.print(f"[bold red]Error: JSON config not found: {servers_json}[/bold red]")
            return
    elif auto_discovery:
        auto_discovery_final = True
        if os.path.exists(DEFAULT_CLAUDE_CONFIG):
            console.print(f"[cyan]Auto-discovering from {DEFAULT_CLAUDE_CONFIG}[/cyan]")
        else:
            console.print(f"[yellow]Claude config not found at {DEFAULT_CLAUDE_CONFIG}[/yellow]")
    else:
        if not mcp_server and not mcp_server_url:
            if os.path.exists(DEFAULT_CLAUDE_CONFIG):
                console.print(f"[cyan]Auto-discovering from {DEFAULT_CLAUDE_CONFIG}[/cyan]")
                auto_discovery_final = True

    if mcp_server:
        for path in mcp_server:
            if not os.path.exists(path):
                console.print(f"[bold red]Error: Server script not found: {path}[/bold red]")
                return

    if trust:
        console.print("[yellow]⚠  Trust mode: all tool calls auto-approved.[/yellow]")

    try:
        await client.connect_to_servers(mcp_server, mcp_server_url, config_path, auto_discovery_final)
        client.auto_load_default_config()

        # CLI --model flag takes priority; else use project preference
        if model != DEFAULT_MODEL:
            client.model_manager.set_model(model)
        elif client._project_context.get("model"):
            client.model_manager.set_model(client._project_context["model"])

        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    app()
