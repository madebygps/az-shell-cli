# ⚡ azsh — Azure Cloud Shell + AI

> What if GitHub Copilot CLI knew Azure Cloud Shell?

A demo prototype showing how the [GitHub Copilot SDK](https://github.com/github/copilot-sdk) could power an AI assistant optimized for Azure Cloud Shell. Built to demonstrate environment-aware intelligence, Azure resource `@mentions`, and Cloud Shell-specific `/slash` commands.

## 🎯 The Pitch

Copilot CLI is great for local dev — but Azure Cloud Shell users have a different workflow. They're doing quick authenticated ops, managing resources across subscriptions, diagnosing AKS clusters, and deploying IaC templates. What if Copilot CLI detected it was running inside Cloud Shell and *adapted* — pre-loading your subscription context, offering Azure-native slash commands, and resolving resource mentions inline?

## ✨ Features

### Slash Commands

| Command  | Description                                      |
|----------|--------------------------------------------------|
| `/sub`   | Switch active Azure subscription                 |
| `/env`   | Show current environment (Cloud Shell vs. local) |
| `/help`  | Show available commands and mentions              |
| `/clear` | Clear the terminal                                |
| `/exit`  | Exit azsh                                         |

### @ Mentions

| Mention            | Description                        | Example                                      |
|--------------------|------------------------------------|----------------------------------------------|
| `@sub`             | Current subscription context       | `@sub show my resource groups`               |
| `@rg:<name>`       | Target a resource group            | `@rg:prod-east list all VMs`                 |
| `@vm:<name>`       | Target a specific VM               | `@vm:web-01 show me the CPU usage`           |
| `@aks:<name>`      | Target an AKS cluster              | `@aks:k8s-prod get failing pods`             |
| `@file:<path>`     | Attach a local file for context    | `@file:main.bicep deploy this template`      |

### Environment-Aware

- Auto-detects Azure Cloud Shell vs local terminal
- Adjusts system prompt, tool suggestions, and auth guidance

### Safety First

- Destructive commands (`delete`, `destroy`, `rm -rf`) require explicit confirmation
- Agent asks permission before executing dangerous operations

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) installed and authenticated
- Azure CLI (`az`) installed (pre-installed in Cloud Shell)

### Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
uv sync
```

### Run

```bash
uv run azsh
```

### In Azure Cloud Shell

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# Install Copilot CLI
curl -fsSL https://gh.io/copilot-install | bash

# Clone and install
git clone https://github.com/madebygps/az-shell-cli.git
cd az-shell-cli
uv sync

# Auth with GitHub (first time only)
copilot        # then type /login

# Run — Cloud Shell is auto-detected!
uv run azsh
```

## 💡 Example Usage

```
azsh> /env
╭─ Environment ────────────────────────╮
│ Environment: Azure Cloud Shell       │
│ User: gps@microsoft.com             │
│ Subscription: Visual Studio Enterprise│
│ Tools: az, kubectl, helm, terraform  │
╰──────────────────────────────────────╯

azsh> @rg:prod-east what VMs are running?
⟳ Resolving @rg:prod-east...
Based on the resources in your prod-east resource group,
you have 3 VMs running: web-01, web-02, and api-server...

azsh> create a storage account in eastus for blob storage
🤖 I'll create a storage account for you:
az storage account create --name mystorageacct --resource-group prod-east --location eastus --sku Standard_LRS
⚠️ Proceed? (y/n)
```

## 🏗️ Architecture

```
azsh (Python CLI)
     ↓
GitHub Copilot SDK (github-copilot-sdk)
     ↓ JSON-RPC
Copilot CLI (server mode)
     ↓
Azure Cloud Shell / Local Terminal
```

## 🛠️ Built With

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk) — the same engine behind Copilot CLI
- [Rich](https://github.com/Textualize/rich) — terminal formatting
- [Pydantic](https://github.com/pydantic/pydantic) — tool parameter schemas

## 📝 License

MIT
