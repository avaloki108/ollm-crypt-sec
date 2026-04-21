"""Human-in-the-Loop (HIL) manager for tool execution confirmations.

Supports per-tool-type permission tiers:
  READ  -- always allowed, no confirmation
  WRITE -- confirm once per session (or when HIL enabled)
  SHELL -- always confirm (unless trust_mode)
  MCP   -- follows global HIL enabled/disabled setting
"""
from enum import Enum
from typing import Set

from rich.prompt import Prompt
from rich.console import Console


class PermissionTier(Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    MCP = "mcp"


# Built-in tool permission mapping (keyed by qualified name with 'builtin.' prefix)
_BUILTIN_PERMISSIONS: dict = {
    "builtin.Read": PermissionTier.READ,
    "builtin.ListDir": PermissionTier.READ,
    "builtin.Glob": PermissionTier.READ,
    "builtin.Grep": PermissionTier.READ,
    "builtin.GitStatus": PermissionTier.READ,
    "builtin.GitLog": PermissionTier.READ,
    "builtin.GitDiff": PermissionTier.READ,
    "builtin.Write": PermissionTier.WRITE,
    "builtin.Edit": PermissionTier.WRITE,
    "builtin.GitCommit": PermissionTier.WRITE,
    "builtin.Shell": PermissionTier.SHELL,
}


class HumanInTheLoopManager:
    """Manages Human-in-the-Loop confirmations for tool execution."""

    def __init__(self, console: Console, trust_mode: bool = False):
        self.console = console
        self._hil_enabled = True
        self._trust_mode = trust_mode
        # Track write tools approved this session (approve-once behaviour)
        self._session_approved_writes: Set[str] = set()

    # ── Public API ──────────────────────────────────────────────────

    def is_enabled(self) -> bool:
        return self._hil_enabled

    def set_trust_mode(self, trust: bool) -> None:
        self._trust_mode = trust

    def toggle(self) -> None:
        if self.is_enabled():
            self.set_enabled(False)
            self.console.print("[yellow]🤖 HIL confirmations disabled[/yellow]")
            self.console.print("[dim]Tool calls will proceed automatically.[/dim]")
        else:
            self.set_enabled(True)
            self.console.print("[green]🧑‍💻 HIL confirmations enabled[/green]")
            self.console.print("[dim]You will be prompted to confirm each tool call.[/dim]")

    def set_enabled(self, enabled: bool) -> None:
        self._hil_enabled = enabled

    async def request_tool_confirmation(self, tool_name: str, tool_args: dict) -> bool:
        """Return True if the tool should be executed.

        Permission tiers:
          READ  -> always True
          WRITE -> True if trust_mode or HIL disabled; else ask-once per session
          SHELL -> True if trust_mode; always ask otherwise
          MCP   -> True if trust_mode or HIL disabled; else prompt
        """
        if self._trust_mode:
            return True

        tier = _BUILTIN_PERMISSIONS.get(tool_name, PermissionTier.MCP)

        if tier == PermissionTier.READ:
            return True

        if tier == PermissionTier.WRITE:
            if not self.is_enabled():
                return True
            # Approve once per session per tool
            if tool_name in self._session_approved_writes:
                return True
            result = await self._ask_confirmation(tool_name, tool_args, tier)
            if result:
                self._session_approved_writes.add(tool_name)
            return result

        if tier == PermissionTier.SHELL:
            return await self._ask_confirmation(tool_name, tool_args, tier)

        # MCP tools: follow global HIL setting
        if not self.is_enabled():
            return True
        return await self._ask_confirmation(tool_name, tool_args, tier)

    # ── Internal helpers ────────────────────────────────────────────

    async def _ask_confirmation(
        self, tool_name: str, tool_args: dict, tier: PermissionTier
    ) -> bool:
        self.console.print("\n[bold yellow]🧑‍💻 Tool Confirmation Required[/bold yellow]")
        self.console.print(f"[cyan]Tool:[/cyan] [bold]{tool_name}[/bold]  "
                           f"[dim]({tier.value} permission)[/dim]")

        if tool_args:
            self.console.print("[cyan]Arguments:[/cyan]")
            for key, value in tool_args.items():
                display = str(value)
                if len(display) > 60:
                    display = display[:57] + "..."
                self.console.print(f"  • {key}: {display}")
        else:
            self.console.print("[cyan]Arguments:[/cyan] [dim]none[/dim]")

        self.console.print()
        self.console.print("[bold cyan]Options:[/bold cyan]")
        self.console.print("  [green]y/yes[/green]     - Execute")
        self.console.print("  [red]n/no[/red]      - Skip this call")
        if tier == PermissionTier.WRITE:
            self.console.print("  [blue]always[/blue]   - Execute and approve all future calls to this tool")
        self.console.print("  [yellow]disable[/yellow]  - Disable HIL confirmations entirely")
        self.console.print()

        choices = ["y", "yes", "n", "no", "disable"]
        if tier == PermissionTier.WRITE:
            choices.append("always")

        choice = Prompt.ask(
            "[bold]Execute?[/bold]",
            choices=choices,
            default="y",
            show_choices=False,
        ).lower()

        if choice == "disable":
            self.toggle()
            execute_current = Prompt.ask(
                "[bold]Execute this current call?[/bold]",
                choices=["y", "yes", "n", "no"],
                default="y",
            ).lower()
            return execute_current in ("y", "yes")

        if choice == "always" and tier == PermissionTier.WRITE:
            self._session_approved_writes.add(tool_name)
            return True

        if choice in ("n", "no"):
            self.console.print("[yellow]⏭️  Tool call skipped[/yellow]")
            return False

        return True  # y/yes
