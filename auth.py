#!/usr/bin/env python3
"""
telemcp — First-time Telegram authentication.

Run once to create the session file.  After that, server.py starts without
any interactive input.

Usage:
    python auth.py [--config config.json]
"""
import argparse
import asyncio
import os
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def authenticate(config) -> None:
    from tg import build_proxy

    session_dir = os.path.dirname(config.session_file)
    if session_dir:
        os.makedirs(session_dir, exist_ok=True)

    proxy, conn_cls = build_proxy(config.proxy)
    kwargs = {}
    if proxy:
        kwargs["proxy"] = proxy
    if conn_cls:
        kwargs["connection"] = conn_cls

    print(f"Connecting to Telegram (api_id={config.api_id}) …")
    client = TelegramClient(
        config.session_file, config.api_id, config.api_hash, **kwargs
    )
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        print(f"Already authorized as: {name} (@{me.username})")
        print(f"Session file: {config.session_file}")
        await client.disconnect()
        return

    phone = input("Phone number (with country code, e.g. +79001234567): ").strip()
    await client.send_code_request(phone)
    code = input("Enter the code from Telegram: ").strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = input("Two-factor authentication password: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    name = f"{me.first_name or ''} {me.last_name or ''}".strip()
    print(f"\nAuthorized as: {name} (@{me.username})")
    print(f"Session saved to: {config.session_file}")

    await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="telemcp — first-time Telegram authentication")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    args = parser.parse_args()

    from config import Config
    config = Config.load(args.config)

    asyncio.run(authenticate(config))


if __name__ == "__main__":
    main()
