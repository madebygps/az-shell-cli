"""GitHub Copilot SDK client setup and session management for azsh."""

import os

from copilot import CopilotClient
from rich.console import Console

from azsh.system_prompt import get_system_prompt
from azsh.tools import all_tools

console = Console()

DESTRUCTIVE_KEYWORDS = [
    "delete",
    "destroy",
    "remove",
    "drop",
    "purge",
    "az group delete",
    "terraform destroy",
    "kubectl delete",
    "rm -rf",
]


def detect_cloud_shell() -> bool:
    """Returns True if running inside Azure Cloud Shell."""
    return bool(os.environ.get("CLOUD_SHELL_ID") or os.environ.get("ACC_CLOUD"))


OUR_TOOLS = {"run_command", "get_azure_context"}


async def on_pre_tool_use(input, invocation) -> dict:
    """Safety hook that shows tool activity and prompts for destructive commands."""
    tool_name = input.get("toolName", "unknown")
    if tool_name not in OUR_TOOLS:
        return {"permissionDecision": "allow"}
    if tool_name == "run_command":
        command = str(input.get("toolArgs", {}).get("command", input.get("input", {}).get("command", "")))
        console.print(f"[dim]🔧 Running: {command}[/dim]")
        if any(kw in command.lower() for kw in DESTRUCTIVE_KEYWORDS):
            return {"permissionDecision": "ask"}
    else:
        console.print(f"[dim]🔧 {tool_name}[/dim]")
    return {"permissionDecision": "allow"}


async def on_post_tool_use(input, invocation) -> dict:
    """Show when a tool call completes."""
    tool_name = input.get("toolName", "unknown")
    if tool_name in OUR_TOOLS:
        console.print(f"[dim]✓ {tool_name} done[/dim]")
    return {}


async def handle_user_input(request, invocation) -> dict:
    """Handle agent-initiated questions by prompting the user."""
    question = request.get("question", request.get("prompt", ""))
    choices = request.get("choices")
    console.print(f"\n[bold yellow]🤖 Agent asks:[/bold yellow] {question}")
    if choices:
        for i, choice in enumerate(choices, 1):
            console.print(f"  [cyan]{i}.[/cyan] {choice}")
    answer = input("> ")
    return {"answer": answer, "wasFreeform": True}


async def create_agent():
    """Create and start a Copilot client and session.

    Returns:
        tuple[CopilotClient, Session]: The client and configured session.
    """
    client = CopilotClient()
    await client.start()

    is_cloud_shell = detect_cloud_shell()
    system_prompt = get_system_prompt()

    session = await client.create_session(
        {
            "model": "gpt-4.1",
            "streaming": True,
            "tools": all_tools,
            "system_message": {"content": system_prompt},
            "hooks": {
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
            },
            "on_user_input_request": handle_user_input,
        }
    )

    return client, session


async def cleanup(client, session) -> None:
    """Destroy the session and stop the client gracefully."""
    try:
        await session.destroy()
    finally:
        await client.stop()
