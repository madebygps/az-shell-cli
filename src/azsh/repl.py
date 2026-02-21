"""Interactive REPL loop for azsh."""

import asyncio
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.panel import Panel

from copilot.generated.session_events import SessionEventType

from azsh.agent import cleanup, create_agent, detect_cloud_shell
from azsh.commands import handle_command
from azsh.mentions import resolve_mentions

console = Console()

SLASH_COMMANDS = {
    "/sub": "Show/switch Azure subscription",
    "/env": "Show environment info, user, and available tools",
    "/help": "Show available commands and @ mentions",
    "/clear": "Clear the screen",
    "/exit": "Exit azsh",
    "/quit": "Exit azsh",
}

AT_MENTIONS = {
    "@sub": "Current subscription context",
    "@rg:": "Resource group — @rg:<name>",
    "@vm:": "Virtual machine — @vm:<name>",
    "@aks:": "AKS cluster — @aks:<name>",
    "@file:": "File contents — @file:<path>",
}


class AzshCompleter(Completer):
    """Autocomplete for slash commands and @ mentions."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/"):
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text), display_meta=desc)

        # Complete @ mentions at any position
        # Find the last @ in the text
        at_pos = text.rfind("@")
        if at_pos >= 0:
            at_text = text[at_pos:]
            for mention, desc in AT_MENTIONS.items():
                if mention.startswith(at_text):
                    yield Completion(
                        mention,
                        start_position=-len(at_text),
                        display_meta=desc,
                    )


async def run_repl():
    """Run the interactive azsh REPL."""
    # Azure-inspired ASCII banner — use plain ANSI since Rich markup can't nest well here
    BLUE = "\033[38;5;33m"
    CYAN = "\033[38;5;44m"
    WHITE = "\033[1;37m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    print(f"""{CYAN}
    ╭──────────────────────────────────────────╮
    │                                          │
    │   {BLUE}█████╗ ███████╗███████╗██╗  ██╗{CYAN}       │
    │   {BLUE}██╔══██╗╚══███╔╝██╔════╝██║  ██║{CYAN}       │
    │   {BLUE}███████║  ███╔╝ ███████╗███████║{CYAN}       │
    │   {BLUE}██╔══██║ ███╔╝  ╚════██║██╔══██║{CYAN}       │
    │   {BLUE}██║  ██║███████╗███████║██║  ██║{CYAN}       │
    │   {DIM}╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝{CYAN}       │
    │                                          │
    │   {WHITE}Azure Cloud Shell + AI{CYAN}     {DIM}v0.1.0{CYAN}   │
    │   {DIM}Powered by GitHub Copilot SDK{CYAN}          │
    │                                          │
    ╰──────────────────────────────────────────╯{RESET}
    """)

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

    prompt_session = PromptSession(
        completer=AzshCompleter(),
        complete_while_typing=True,
    )

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
                user_input = (await prompt_session.prompt_async(
                    HTML("<cyan><b>azsh&gt;</b></cyan> "),
                )).strip()
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

            console.print("[dim]⏳ Thinking...[/dim]")
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
