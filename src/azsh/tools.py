"""Custom tools for the Azure Shell CLI agent."""

import asyncio
import json
from typing import Optional

from pydantic import BaseModel, Field

from copilot.tools import define_tool


class RunCommandParams(BaseModel):
    command: str = Field(description="The shell command to execute")
    working_directory: Optional[str] = Field(
        default=None, description="Working directory for command execution"
    )


class GetAzureContextParams(BaseModel):
    pass


@define_tool(
    description=(
        "Execute a shell command and return the output. Use this to run az CLI,"
        " kubectl, helm, terraform, git, or any other command-line tool."
    )
)
async def run_command(params: RunCommandParams) -> str:
    try:
        process = await asyncio.create_subprocess_shell(
            params.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=params.working_directory,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except asyncio.TimeoutError:
        process.kill()
        return "Error: Command timed out after 60 seconds."

    result_parts = [f"Exit code: {process.returncode}"]
    if stdout:
        result_parts.append(f"Stdout:\n{stdout.decode()}")
    if stderr:
        result_parts.append(f"Stderr:\n{stderr.decode()}")
    return "\n".join(result_parts)


@define_tool(
    description=(
        "Get the current Azure context including signed-in user, active"
        " subscription, and tenant information."
    )
)
async def get_azure_context(params: GetAzureContextParams) -> str:
    try:
        process = await asyncio.create_subprocess_shell(
            "az account show --output json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except asyncio.TimeoutError:
        process.kill()
        return "Error: Timed out retrieving Azure context."

    if process.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else "Unknown error"
        return (
            f"Error: Failed to get Azure context. {error_msg}\n"
            "Make sure the Azure CLI is installed and you are logged in"
            " (run 'az login')."
        )

    try:
        account = json.loads(stdout.decode())
    except json.JSONDecodeError:
        return "Error: Could not parse Azure CLI output."

    user = account.get("user", {})
    return (
        f"Subscription: {account.get('name', 'N/A')}\n"
        f"Subscription ID: {account.get('id', 'N/A')}\n"
        f"Tenant ID: {account.get('tenantId', 'N/A')}\n"
        f"User: {user.get('name', 'N/A')} ({user.get('type', 'N/A')})\n"
        f"Cloud: {account.get('cloudName', 'N/A')}\n"
        f"State: {account.get('state', 'N/A')}"
    )


all_tools = [run_command, get_azure_context]
