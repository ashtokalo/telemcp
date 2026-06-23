#!/usr/bin/env python3
"""Quick connectivity smoke test."""
import asyncio
import argparse
import sys

from .config import Config
from .tg import TelegramReader
from .whitelist import Whitelist


async def run(config_path: str) -> None:
    config = Config.load(config_path)
    tg = TelegramReader(config)

    print("Connecting to Telegram...")
    try:
        await tg.connect()
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    print("OK\n")

    print("Folders:")
    folders = await tg.get_folders()
    if folders:
        for f in folders:
            print(f"  {f['id']:>4}  {f['name']}")
    else:
        print("  (none)")

    print("\nFirst 15 dialogs (no whitelist filter):")
    dialogs = await tg.get_dialogs()
    for d in dialogs[:15]:
        unread = f"  [{d['unread_count']} unread]" if d['unread_count'] else ""
        print(f"  {str(d['id']):>20}  {d['type']:<12}  {d['name']}{unread}")
    if len(dialogs) > 15:
        print(f"  ... and {len(dialogs) - 15} more")

    wl = Whitelist(config.whitelist)
    if wl.is_configured():
        print("\nDialogs passing whitelist filter:")
        allowed = await tg.get_dialogs(whitelist=wl)
        for d in allowed:
            unread = f"  [{d['unread_count']} unread]" if d['unread_count'] else ""
            print(f"  {str(d['id']):>20}  {d['type']:<12}  {d['name']}{unread}")
    else:
        print("\nWhitelist is empty - skipping filtered check.")

    await tg.disconnect()
    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
