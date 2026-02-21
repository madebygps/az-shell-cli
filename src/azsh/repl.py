"""Interactive REPL loop for azsh."""

import asyncio
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown

from copilot.generated.session_events import SessionEventType

from azsh.agent import cleanup, create_agent
from azsh.commands import handle_command
from azsh.mentions import resolve_mentions
from azsh.resource_cache import get_active_rg, get_resource_completions

console = Console()

SLASH_COMMANDS = {
    "/sub": "Show/switch Azure subscription",
    "/rg": "Set working resource group",
    "/help": "Show available commands and @ mentions",
    "/clear": "Clear the screen",
    "/exit": "Exit azsh",
    "/quit": "Exit azsh",
}

STATIC_MENTIONS = {
    "@sub": "Current subscription context",
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
        at_pos = text.rfind("@")
        if at_pos >= 0:
            at_text = text[at_pos:]

            # Static mentions
            for mention, desc in STATIC_MENTIONS.items():
                if mention.startswith(at_text):
                    yield Completion(
                        mention,
                        start_position=-len(at_text),
                        display_meta=desc,
                    )

            # Dynamic resources from active RG
            rg = get_active_rg()
            if rg:
                for mention, desc in get_resource_completions():
                    if mention.startswith(at_text):
                        yield Completion(
                            mention,
                            start_position=-len(at_text),
                            display_meta=desc,
                        )


async def run_repl():
    """Run the interactive azsh REPL."""
    # Banner using Rich for reliable rendering
    console.print()
    console.print("[bold blue]  ╔═╗╔═══╗╔═══╗╦  ╦[/bold blue]")
    console.print("[bold blue]  ╠═╣  ╔═╝╚══╗║╠══╣[/bold blue]")
    console.print("[bold blue]  ╩ ╩╚═══╝╚═══╝╩  ╩[/bold blue]")
    console.print()
    console.print("[bold white]  Azure Cloud Shell + AI[/bold white]  [dim]v0.1.0[/dim]")
    console.print("[dim]  Powered by GitHub Copilot SDK[/dim]")
    console.print()

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
        response_buffer = []

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = event.data.delta_content or ""
                response_buffer.append(delta)
                # Show a dot for progress while streaming
                sys.stdout.write(".")
                sys.stdout.flush()

        session.on(handle_event)

        while True:
            try:
                active_rg = get_active_rg()
                if active_rg:
                    prompt_text = HTML(
                        f"<cyan><b>azsh</b></cyan> <ansiblue>[{active_rg}]</ansiblue><cyan><b>&gt;</b></cyan> "
                    )
                else:
                    prompt_text = HTML("<cyan><b>azsh&gt;</b></cyan> ")
                user_input = (await prompt_session.prompt_async(prompt_text)).strip()
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

            # Prepend active resource group context if set
            active_rg = get_active_rg()
            if active_rg:
                resolved_text = (
                    f"[Active Resource Group: {active_rg}]\n"
                    f"When I say 'this resource group' I mean '{active_rg}'.\n\n"
                    f"{resolved_text}"
                )

            console.print("[dim]⏳ Thinking...[/dim]")
            response_buffer.clear()
            try:
                await session.send_and_wait({"prompt": resolved_text, "timeout": 300})
            except asyncio.TimeoutError:
                console.print("\n[yellow]⚠ Response timed out.[/yellow]")
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]")

            # Render the collected response as markdown
            if response_buffer:
                full_response = "".join(response_buffer)
                # Clear the progress dots
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
                console.print(Markdown(full_response))
            print()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")
    finally:
        await cleanup(client, session)
