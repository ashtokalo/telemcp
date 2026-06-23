"""Unified CLI entry point for telemcp."""
import argparse
import asyncio
import json
import sys

# ---------------------------------------------------------------------------
# Shared parent parsers
# ---------------------------------------------------------------------------

_common = argparse.ArgumentParser(add_help=False)
_common.add_argument(
    "--config", default="config.json", metavar="FILE",
    help="path to config.json (default: config.json)",
)

_io = argparse.ArgumentParser(add_help=False)
_io.add_argument(
    "--text", action="store_true",
    help="output human-readable text instead of JSON",
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print(data, text: bool, formatter) -> None:
    if text:
        print(formatter(data))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _fmt_folders(data) -> str:
    if not data:
        return "No folders."
    lines = [f"  {f['id']:>4}  {f['name']}" for f in data]
    return "Folders:\n" + "\n".join(lines)


def _fmt_dialogs(data) -> str:
    if not data:
        return "No dialogs."
    lines = []
    for d in data:
        unread = f"  [{d['unread_count']} unread]" if d["unread_count"] else ""
        lines.append(f"  {str(d['id']):>20}  {d['type']:<12}  {d['name']}{unread}")
    return f"Dialogs ({len(data)}):\n" + "\n".join(lines)


def _fmt_messages(data) -> str:
    if not data:
        return "No messages."
    lines = []
    for m in data:
        date = (m.get("date") or "")[:16].replace("T", " ")
        sender = m.get("sender") or ""
        text = m.get("text") or f"[{m.get('media') or 'media'}]"
        text = text[:200].replace("\n", " ")
        lines.append(f"  [{date}] {sender}: {text}")
    return f"Messages ({len(data)}):\n" + "\n".join(lines)


def _fmt_unread(data) -> str:
    folder = data.get("folder") or "All chats"
    count = data["chats_with_unread"]
    lines = [f"{folder} — {count} chat(s) with unread messages\n"]
    for chat in data.get("chats", []):
        lines.append(f"  {chat['chat_name']}  [{chat['unread_count']} unread]")
        for m in chat.get("messages", []):
            date = (m.get("date") or "")[:16].replace("T", " ")
            sender = m.get("sender") or ""
            text = m.get("text") or f"[{m.get('media') or 'media'}]"
            text = text[:200].replace("\n", " ")
            lines.append(f"    [{date}] {sender}: {text}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _cmd_folders(args) -> None:
    from .config import Config
    from .tg import TelegramReader

    tg = TelegramReader(Config.load(args.config))
    await tg.connect()
    try:
        _print(await tg.get_folders(), args.text, _fmt_folders)
    finally:
        await tg.disconnect()


async def _cmd_dialogs(args) -> None:
    from .config import Config
    from .tg import TelegramReader
    from .whitelist import Whitelist

    config = Config.load(args.config)
    tg = TelegramReader(config)
    wl = Whitelist(config.whitelist)
    await tg.connect()
    try:
        data = await tg.get_dialogs(folder_id=args.folder_id, whitelist=wl)
        _print(data, args.text, _fmt_dialogs)
    finally:
        await tg.disconnect()


async def _cmd_messages(args) -> None:
    from .config import Config
    from .tg import TelegramReader
    from .whitelist import Whitelist

    config = Config.load(args.config)
    tg = TelegramReader(config)
    wl = Whitelist(config.whitelist)
    await tg.connect()
    try:
        data = await tg.get_messages(
            chat_ref=args.chat_ref,
            limit=args.limit,
            unread_only=args.unread_only,
            since_hours=args.since_hours,
            since_message_id=args.since_message_id,
            whitelist=wl,
        )
        _print(data, args.text, _fmt_messages)
    finally:
        await tg.disconnect()


async def _cmd_unread(args) -> None:
    from .config import Config
    from .tg import TelegramReader
    from .whitelist import Whitelist

    config = Config.load(args.config)
    tg = TelegramReader(config)
    wl = Whitelist(config.whitelist)
    await tg.connect()
    try:
        data = await tg.get_unread_summary(
            folder_id=args.folder_id,
            max_per_chat=args.max_per_chat,
            whitelist=wl,
        )
        _print(data, args.text, _fmt_unread)
    finally:
        await tg.disconnect()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemcp",
        description="Read-only Telegram MCP server and CLI.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    # auth
    p_auth = sub.add_parser("auth", parents=[_common],
                            help="authenticate with Telegram (run once)")
    p_auth.add_argument("--qr", action="store_true",
                        help="log in by scanning a QR code instead of phone + code")
    p_auth.add_argument("--verbose", "-v", action="store_true",
                        help="show Telethon debug logs")

    # connection
    sub.add_parser("connection", parents=[_common],
                   help="verify the connection to Telegram")

    # folders
    sub.add_parser("folders", parents=[_common, _io],
                   help="list all Telegram folder filters")

    # dialogs
    p_dialogs = sub.add_parser("dialogs", parents=[_common, _io],
                               help="list dialogs (chats, groups, channels)")
    p_dialogs.add_argument(
        "--folder-id", type=int, default=None, metavar="ID",
        help="limit to dialogs inside this folder (ID from 'telemcp folders')",
    )

    # messages
    p_messages = sub.add_parser("messages", parents=[_common, _io],
                                help="read messages from a chat")
    p_messages.add_argument("chat_ref",
                            help="numeric ID, @username, or t.me link")
    p_messages.add_argument("--limit", type=int, default=50, metavar="N",
                            help="max messages to return (default: 50, max: 200)")
    p_messages.add_argument("--unread-only", action="store_true",
                            help="return only unread messages")
    p_messages.add_argument("--since-hours", type=float, default=None, metavar="N",
                            help="return only messages from the last N hours")
    p_messages.add_argument("--since-message-id", type=int, default=None, metavar="ID",
                            help="return only messages with ID greater than this value")

    # unread
    p_unread = sub.add_parser("unread", parents=[_common, _io],
                              help="digest of unread messages across whitelisted chats")
    p_unread.add_argument(
        "--folder-id", type=int, default=None, metavar="ID",
        help="scope to a specific folder",
    )
    p_unread.add_argument(
        "--max-per-chat", type=int, default=20, metavar="N",
        help="max messages per chat (default: 20)",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Commands handled elsewhere (auth and connection have their own flow)
    if args.command == "auth":
        import logging
        from .config import Config
        from .auth import authenticate

        if args.verbose:
            logging.basicConfig(level=logging.DEBUG,
                                format="%(asctime)s %(name)s %(levelname)s %(message)s",
                                stream=sys.stderr)
        else:
            logging.basicConfig(level=logging.WARNING,
                                format="%(asctime)s %(levelname)s %(message)s",
                                stream=sys.stderr)
        try:
            asyncio.run(authenticate(Config.load(args.config), use_qr=args.qr))
        except KeyboardInterrupt:
            print("\nCancelled.", file=sys.stderr)
            sys.exit(0)
        return

    if args.command == "connection":
        from .test_connection import run as connection_run
        from .config import Config
        try:
            asyncio.run(connection_run(args.config))
        except KeyboardInterrupt:
            print("\nCancelled.", file=sys.stderr)
            sys.exit(0)
        return

    _dispatch = {
        "folders":  _cmd_folders,
        "dialogs":  _cmd_dialogs,
        "messages": _cmd_messages,
        "unread":   _cmd_unread,
    }

    if args.command not in _dispatch:
        parser.print_help()
        sys.exit(0)

    try:
        asyncio.run(_dispatch[args.command](args))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(0)
    except PermissionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
