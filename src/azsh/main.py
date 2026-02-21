"""Entry point for azsh CLI."""

import asyncio

from azsh.repl import run_repl


def main():
    asyncio.run(run_repl())


if __name__ == "__main__":
    main()
