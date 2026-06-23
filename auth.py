#!/usr/bin/env python3
"""
telemcp — First-time Telegram authentication.

Run once to create the session file.  After that, server.py starts without
any interactive input.

Usage:
    python auth.py [--config config.json]           # phone + code
    python auth.py [--config config.json] --qr      # QR code (scan with existing Telegram app)
"""
import argparse
import asyncio
import logging
import os
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def _finish(client) -> None:
    """Print who we logged in as and disconnect."""
    me = await client.get_me()
    name = f"{me.first_name or ''} {me.last_name or ''}".strip()
    print(f"\nAuthorized as: {name} (@{me.username})")
    await client.disconnect()


async def auth_phone(client) -> None:
    phone = input("Phone number (with country code, e.g. +79001234567): ").strip()
    await client.send_code_request(phone)
    code = input("Enter the code from Telegram: ").strip()
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = input("Two-factor authentication password: ").strip()
        await client.sign_in(password=password)


async def auth_qr(client) -> None:
    try:
        import qrcode
    except ImportError:
        print("qrcode package is required for QR login: pip install qrcode", file=sys.stderr)
        sys.exit(1)

    print("Generating QR code...")
    print("Open Telegram on your phone or desktop, go to:")
    print("  Settings -> Devices -> Link Desktop Device")
    print("Then scan the QR code below.\n")

    qr_login = await client.qr_login()

    def _print_qr(url: str) -> None:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print()

    _print_qr(qr_login.url)

    try:
        await qr_login.wait(timeout=60)
    except asyncio.TimeoutError:
        print("QR code expired. Run auth.py again.", file=sys.stderr)
        sys.exit(1)
    except SessionPasswordNeededError:
        password = input("Two-factor authentication password: ").strip()
        await client.sign_in(password=password)


async def authenticate(config, use_qr: bool) -> None:
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

    print(f"Connecting to Telegram (api_id={config.api_id}) ...")
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

    if use_qr:
        await auth_qr(client)
    else:
        await auth_phone(client)

    await _finish(client)
    print(f"Session saved to: {config.session_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="telemcp — first-time Telegram authentication")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--qr", action="store_true", help="Log in by scanning a QR code (no SMS needed)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show Telethon debug logs")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stderr,
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s %(levelname)s %(message)s",
            stream=sys.stderr,
        )

    from config import Config
    config = Config.load(args.config)

    asyncio.run(authenticate(config, use_qr=args.qr))


if __name__ == "__main__":
    main()
