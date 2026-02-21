"""Interactive REPL loop for azsh."""

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel

from copilot.generated.session_events import SessionEventType

from azsh.agent import cleanup, create_agent, detect_cloud_shell
from azsh.commands import handle_command
from azsh.mentions import resolve_mentions

console = Console()


async def run_repl():
    """Run the interactive azsh REPL."""
    console.print(
        Panel(
            "[bold cyan]⚡ azsh — Azure Cloud Shell + AI[/bold cyan]\n"
            "[dim]Powered by GitHub Copilot SDK[/dim]",
            expand=False,
        )
    )

    env = "Cloud Shell" if detect_cloud_shell() else "Local"
    console.print(f"[dim]Environment: {env}[/dim]")
    console.print("[dim]Type /help for commands, @ to mention Azure resources[/dim]\n")

    try:
        client, session = await create_agent()
    except Exception as e:
        console.print(
            f"[bold red]Error:[/bold red] Failed to initialize Copilot agent: {e}"
        )
        console.print(
            "[dim]Make sure GitHub Copilot CLI is installed and authenticated.[/dim]"
        )
        return

    try:
        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = event.data.delta_content or ""
                sys.stdout.write(delta)
                sys.stdout.flush()
            elif event.type == SessionEventType.SESSION_IDLE:
                print()

        session.on(handle_event)

        while True:
            try:
                user_input = input("azsh> ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            result = await handle_command(user_input)
            if result == "exit":
                break
            if result == "clear":
                console.clear()
                continue
            if result == "handled":
                continue

            resolved_text = await resolve_mentions(user_input)

            try:
                await session.send_and_wait({"prompt": resolved_text, "timeout": 300})
            except asyncio.TimeoutError:
                console.print("\n[yellow]⚠ Response timed out. The agent may still be working — try a simpler request.[/yellow]")
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]")
            print()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")
    finally:
        await cleanup(client, session)
