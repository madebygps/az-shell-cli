"""Resource cache for Azure resources in the active resource group."""

import asyncio
import json
from typing import Optional

from rich.console import Console

console = Console()

# Active resource group and cached resources
_active_rg: Optional[str] = None
_cached_resources: list[dict] = []
_fetch_task: Optional[asyncio.Task] = None


def get_active_rg() -> Optional[str]:
    return _active_rg


def get_cached_resources() -> list[dict]:
    return _cached_resources


async def _fetch_resources(rg_name: str) -> list[dict]:
    """Fetch resources in a resource group via az CLI."""
    try:
        process = await asyncio.create_subprocess_shell(
            f"az resource list -g {rg_name} --output json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        if process.returncode != 0:
            return []
        return json.loads(stdout.decode())
    except (asyncio.TimeoutError, json.JSONDecodeError):
        return []


async def set_active_rg(rg_name: str) -> None:
    """Set the active resource group and prefetch its resources."""
    global _active_rg, _cached_resources, _fetch_task

    _active_rg = rg_name
    _cached_resources = []

    # Cancel any in-flight fetch
    if _fetch_task and not _fetch_task.done():
        _fetch_task.cancel()

    async def _do_fetch():
        global _cached_resources
        _cached_resources = await _fetch_resources(rg_name)
        count = len(_cached_resources)
        console.print(f"[dim]  ↳ {count} resource(s) loaded, use @ to mention them[/dim]")

    _fetch_task = asyncio.create_task(_do_fetch())


def get_resource_completions() -> list[tuple[str, str]]:
    """Return (mention, description) tuples for cached resources."""
    completions = []
    for r in _cached_resources:
        name = r.get("name", "")
        rtype = r.get("type", "")
        location = r.get("location", "")
        # Shorten type: Microsoft.Compute/virtualMachines -> vm
        short_type = _short_resource_type(rtype)
        mention = f"@{short_type}:{name}" if short_type else f"@{name}"
        desc = f"{rtype} ({location})"
        completions.append((mention, desc))
    return completions


def _short_resource_type(full_type: str) -> str:
    """Map Azure resource types to short prefixes."""
    mapping = {
        "microsoft.compute/virtualmachines": "vm",
        "microsoft.containerservice/managedclusters": "aks",
        "microsoft.storage/storageaccounts": "storage",
        "microsoft.web/sites": "webapp",
        "microsoft.sql/servers": "sql",
        "microsoft.network/virtualnetworks": "vnet",
        "microsoft.network/networksecuritygroups": "nsg",
        "microsoft.network/publicipaddresses": "pip",
        "microsoft.network/loadbalancers": "lb",
        "microsoft.keyvault/vaults": "kv",
        "microsoft.containerregistry/registries": "acr",
        "microsoft.dbforpostgresql/flexibleservers": "pg",
        "microsoft.dbformysql/flexibleservers": "mysql",
        "microsoft.insights/components": "appinsights",
        "microsoft.operationalinsights/workspaces": "loganalytics",
    }
    return mapping.get(full_type.lower(), "")
