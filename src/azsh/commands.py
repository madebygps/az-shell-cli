"""Slash commands — client-side commands that execute instantly without going through the LLM."""

import asyncio
import subprocess
import json
import os
import shutil
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


async def handle_command(command: str) -> str | None:
    """Handle a slash command. Returns None if not a command, 'handled' if handled, 'exit' to quit, 'clear' to clear."""
    stripped = command.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    handlers = {
        "/sub": _handle_sub,
        "/env": _handle_env,
        "/help": _handle_help,
        "/clear": _handle_clear,
        "/exit": _handle_exit,
        "/quit": _handle_exit,
    }

    handler = handlers.get(cmd)
    if handler is None:
        console.print(f"[red]Unknown command: {cmd}[/red]. Type /help for available commands.")
        return "handled"

    return await handler(arg)


def _run_az(args: str) -> dict | None:
    """Run an az CLI command with JSON output, return parsed JSON or None on failure."""
    try:
        result = subprocess.run(
            f"az {args} --output json",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


async def _handle_sub(arg: str | None) -> str:
    """List subscriptions or switch to a named subscription."""
    if arg:
        result = await asyncio.to_thread(
            subprocess.run,
            f"az account set --subscription {arg!r}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            console.print(f"[green]✓ Switched to subscription:[/green] {arg}")
        else:
            console.print(f"[red]✗ Failed to switch subscription:[/red] {result.stderr.strip()}")
        return "handled"

    data = await asyncio.to_thread(_run_az, "account list")
    if not data:
        console.print("[red]Failed to list subscriptions. Is the Azure CLI installed and logged in?[/red]")
        return "handled"

    table = Table(title="Azure Subscriptions")
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Default", justify="center")

    for sub in data:
        default_marker = "✓" if sub.get("isDefault") else ""
        table.add_row(
            sub.get("name", ""),
            sub.get("id", ""),
            f"[green]{default_marker}[/green]" if default_marker else "",
        )

    console.print(table)
    return "handled"


async def _handle_env(_arg: str | None) -> str:
    """Show current environment information."""
    is_cloud_shell = bool(os.environ.get("CLOUD_SHELL_ID") or os.environ.get("ACC_CLOUD"))
    env_type = "Azure Cloud Shell" if is_cloud_shell else "Local Terminal"

    account = await asyncio.to_thread(_run_az, "account show")
    user = "unknown"
    subscription = "unknown"
    if account:
        user_info = account.get("user", {})
        user = user_info.get("name", "unknown")
        subscription = account.get("name", "unknown")

    tools_to_check = ["az", "kubectl", "helm", "terraform", "git", "gh", "python3", "azcopy", "bicep"]
    available_tools = [t for t in tools_to_check if shutil.which(t)]
    tools_str = ", ".join(f"[green]{t}[/green]" for t in available_tools) if available_tools else "[dim]none[/dim]"

    content = (
        f"[bold]Environment:[/bold] {env_type}\n"
        f"[bold]User:[/bold] {user}\n"
        f"[bold]Subscription:[/bold] {subscription}\n"
        f"[bold]Tools:[/bold] {tools_str}"
    )
    console.print(Panel(content, title="Environment", border_style="blue"))
    return "handled"


async def _handle_help(_arg: str | None) -> str:
    """Show help with available slash commands and @ mentions."""
    cmd_table = Table(title="Slash Commands", show_header=True)
    cmd_table.add_column("Command", style="cyan")
    cmd_table.add_column("Description")
    cmd_table.add_row("/sub [name]", "List subscriptions or switch to one")
    cmd_table.add_row("/env", "Show environment info, user, and available tools")
    cmd_table.add_row("/help", "Show this help message")
    cmd_table.add_row("/clear", "Clear the screen")
    cmd_table.add_row("/exit", "Exit the shell")

    mention_table = Table(title="@ Mentions", show_header=True)
    mention_table.add_column("Mention", style="cyan")
    mention_table.add_column("Description")
    mention_table.add_column("Example", style="dim")
    mention_table.add_row("@sub", "Include current subscription context", "@sub list my resources")
    mention_table.add_row("@rg:<name>", "Include resource group context", "@rg:mygroup show all VMs")
    mention_table.add_row("@vm:<name>", "Include VM context", "@vm:web-server check status")
    mention_table.add_row("@aks:<name>", "Include AKS cluster context", "@aks:prod get node count")
    mention_table.add_row("@file:<path>", "Include file contents as context", "@file:main.bicep deploy this")

    console.print(Panel.fit(cmd_table, border_style="blue"))
    console.print(Panel.fit(mention_table, border_style="blue"))
    return "handled"


async def _handle_clear(_arg: str | None) -> str:
    """Signal the REPL to clear the screen."""
    return "clear"


async def _handle_exit(_arg: str | None) -> str:
    """Signal the REPL to exit."""
    return "exit"
