#!/usr/bin/env python3
"""
telemcp — Read-only Telegram MCP server.

Usage:
    python server.py [--config config.json]

First run:
    python auth.py [--config config.json]
"""
import argparse
import asyncio
import sys

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from config import Config
from tg import TelegramReader
from tools import register_tools
from whitelist import Whitelist


async def main() -> None:
    parser = argparse.ArgumentParser(description="telemcp — read-only Telegram MCP server")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    args = parser.parse_args()

    config = Config.load(args.config)
    tg = TelegramReader(config)
    wl = Whitelist(config.whitelist)

    if not wl.is_configured():
        print(
            "[telemcp] Whitelist is empty. "
            "tg_get_messages and tg_get_unread_summary will refuse all requests. "
            "Use tg_list_folders / tg_list_dialogs to discover IDs, then set the whitelist in config.",
            file=sys.stderr,
            flush=True,
        )

    try:
        await tg.connect()
    except RuntimeError as exc:
        print(f"[telemcp] {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[telemcp] Failed to connect to Telegram: {exc}", file=sys.stderr)
        sys.exit(1)

    server = Server("telemcp")
    register_tools(server, tg, wl)

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="telemcp",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        await tg.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
