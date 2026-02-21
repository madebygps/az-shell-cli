"""Resolve @mentions in user input by querying Azure resources and prepending context."""

import json
import os
import re
import subprocess
from typing import Callable

from rich.console import Console

console = Console()

AZ_TIMEOUT = 10


def _run_az(args: list[str]) -> dict | list | str:
    """Run an az CLI command and return parsed JSON output."""
    cmd = ["az"] + args + ["--output", "json"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=AZ_TIMEOUT
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"az command failed: {' '.join(cmd)}")
    return json.loads(result.stdout)


def _resolve_sub(match: re.Match) -> tuple[str, str]:
    """Resolve @sub — show current subscription context."""
    console.print("[dim]⟳ Resolving @sub...[/dim]")
    # Try Cloud Shell env vars first (instant)
    sub_id = os.environ.get("ACC_USER_SUBSCRIPTION")
    if sub_id:
        tenant_id = os.environ.get("ACC_TID", "unknown")
        location = os.environ.get("ACC_LOCATION", "unknown")
        user = os.environ.get("USER", "unknown")
        session_type = os.environ.get("ACC_SESSION_TYPE", "unknown")
        context = (
            f"[Azure Context: Current Subscription]\n"
            f"Subscription ID: {sub_id}, Tenant: {tenant_id}, "
            f"Region: {location}, User: {user}, Session: {session_type}"
        )
        return context, "the current subscription"
    # Fallback to az CLI
    try:
        info = _run_az(["account", "show"])
        name = info.get("name", "unknown")
        sub_id = info.get("id", "unknown")
        tenant = info.get("tenantId", "unknown")
        user = info.get("user", {}).get("name", "unknown")
        state = info.get("state", "unknown")
        context = (
            f"[Azure Context: Subscription '{name}']\n"
            f"ID: {sub_id}, Tenant: {tenant}, User: {user}, State: {state}"
        )
        return context, "the current subscription"
    except Exception as e:
        return f"[Could not resolve @sub: {e}]", "@sub"


def _resolve_rg(match: re.Match) -> tuple[str, str]:
    """Resolve @rg:<name> — show resource group details and resources."""
    name = match.group(1)
    console.print(f"[dim]⟳ Resolving @rg:{name}...[/dim]")
    try:
        group = _run_az(["group", "show", "-n", name])
        location = group.get("location", "unknown")
        tags = group.get("tags") or {}
        prov_state = group.get("properties", {}).get("provisioningState", "unknown")
        tags_str = ", ".join(f"{k}={v}" for k, v in tags.items()) if tags else "none"

        resources = _run_az(["resource", "list", "-g", name])
        resource_lines = []
        for r in resources:
            r_name = r.get("name", "?")
            r_type = r.get("type", "?")
            r_loc = r.get("location", "?")
            resource_lines.append(f"  - {r_name} ({r_type}) [{r_loc}]")
        resources_text = "\n".join(resource_lines) if resource_lines else "  (none)"

        context = (
            f"[Azure Context: Resource Group '{name}']\n"
            f"Location: {location}, Tags: {tags_str}, Provisioning: {prov_state}\n"
            f"Resources:\n{resources_text}"
        )
        return context, f"resource group '{name}'"
    except Exception as e:
        return f"[Could not resolve @rg:{name}: {e}]", f"@rg:{name}"


def _resolve_vm(match: re.Match) -> tuple[str, str]:
    """Resolve @vm:<name> — show VM details."""
    name = match.group(1)
    console.print(f"[dim]⟳ Resolving @vm:{name}...[/dim]")
    try:
        vms = _run_az(["vm", "list", "-d", "--query", f"[?name=='{name}']"])
        if not vms:
            return f"[Could not resolve @vm:{name}: VM not found]", f"@vm:{name}"
        vm = vms[0]
        size = vm.get("hardwareProfile", {}).get("vmSize", "unknown")
        power_state = vm.get("powerState", "unknown")
        os_type = vm.get("storageProfile", {}).get("osDisk", {}).get("osType", "unknown")
        public_ip = vm.get("publicIps", "none") or "none"
        private_ip = vm.get("privateIps", "none") or "none"
        location = vm.get("location", "unknown")
        rg = vm.get("resourceGroup", "unknown")

        context = (
            f"[Azure Context: VM '{name}']\n"
            f"Resource Group: {rg}, Location: {location}\n"
            f"Size: {size}, OS: {os_type}, Power State: {power_state}\n"
            f"Public IP: {public_ip}, Private IP: {private_ip}"
        )
        return context, f"VM '{name}'"
    except Exception as e:
        return f"[Could not resolve @vm:{name}: {e}]", f"@vm:{name}"


def _resolve_aks(match: re.Match) -> tuple[str, str]:
    """Resolve @aks:<name> — show AKS cluster details."""
    name = match.group(1)
    console.print(f"[dim]⟳ Resolving @aks:{name}...[/dim]")
    try:
        clusters = _run_az(["aks", "list", "--query", f"[?name=='{name}']"])
        if not clusters:
            return f"[Could not resolve @aks:{name}: cluster not found]", f"@aks:{name}"
        cluster = clusters[0]
        version = cluster.get("kubernetesVersion", "unknown")
        fqdn = cluster.get("fqdn", "unknown")
        prov_state = cluster.get("provisioningState", "unknown")

        pools = cluster.get("agentPoolProfiles", [])
        node_info = []
        for pool in pools:
            pool_name = pool.get("name", "?")
            count = pool.get("count", "?")
            vm_size = pool.get("vmSize", "?")
            node_info.append(f"  - {pool_name}: {count} nodes ({vm_size})")
        nodes_text = "\n".join(node_info) if node_info else "  (none)"

        context = (
            f"[Azure Context: AKS Cluster '{name}']\n"
            f"Version: {version}, FQDN: {fqdn}, Provisioning: {prov_state}\n"
            f"Node Pools:\n{nodes_text}"
        )
        return context, f"AKS cluster '{name}'"
    except Exception as e:
        return f"[Could not resolve @aks:{name}: {e}]", f"@aks:{name}"


def _resolve_file(match: re.Match) -> tuple[str, str]:
    """Resolve @file:<path> — read a local file and include its contents."""
    path = match.group(1)
    expanded = os.path.expanduser(path)
    console.print(f"[dim]⟳ Resolving @file:{path}...[/dim]")
    try:
        with open(expanded, "r") as f:
            contents = f.read()
        context = (
            f"[Azure Context: File '{path}']\n"
            f"{contents}"
        )
        return context, f"file '{path}'"
    except FileNotFoundError:
        return f"[Could not resolve @file:{path}: file not found]", f"@file:{path}"
    except Exception as e:
        return f"[Could not resolve @file:{path}: {e}]", f"@file:{path}"


# Ordered list of (pattern, resolver). Checked in order against user input.
MENTION_PATTERNS: list[tuple[str, Callable]] = [
    (r"@sub\b", _resolve_sub),
    (r"@rg:(\S+)", _resolve_rg),
    (r"@vm:(\S+)", _resolve_vm),
    (r"@aks:(\S+)", _resolve_aks),
    (r"@file:(\S+)", _resolve_file),
]


async def resolve_mentions(user_input: str) -> str:
    """Resolve all @mentions in user input and return modified prompt with context prepended."""
    contexts: list[str] = []
    cleaned = user_input

    for pattern, resolver in MENTION_PATTERNS:
        for match in re.finditer(pattern, cleaned):
            try:
                context, replacement = resolver(match)
            except subprocess.TimeoutExpired:
                mention = match.group(0)
                context = f"[Could not resolve {mention}: timed out after {AZ_TIMEOUT}s]"
                replacement = mention
            contexts.append(context)
            cleaned = cleaned.replace(match.group(0), replacement, 1)

    # Clean up extra whitespace from replacements
    cleaned = re.sub(r"  +", " ", cleaned).strip()

    if not contexts:
        return user_input

    preamble = "\n\n".join(contexts)
    return f"{preamble}\n\nUser question: {cleaned}"
