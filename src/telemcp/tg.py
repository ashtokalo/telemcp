"""Telegram client wrapper (read-only) built on Telethon."""
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    Channel,
    Chat,
    DialogFilter,
    DialogFilterDefault,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    User,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_chat_ref(ref) -> Tuple[Any, Optional[int]]:
    """
    Parse a chat reference.  Returns (chat_id, message_id_hint).
    chat_id may be int, '@username' str, or raw string for Telethon to resolve.
    message_id_hint is the message ID embedded in a t.me URL (or None).
    """
    if isinstance(ref, int):
        return ref, None

    ref = str(ref).strip()

    # https://t.me/c/1668839992/5699  — private channel
    m = re.match(r"https?://t\.me/c/(\d+)(?:/(\d+))?", ref)
    if m:
        chat_id = -int("100" + m.group(1))
        msg_id = int(m.group(2)) if m.group(2) else None
        return chat_id, msg_id

    # https://t.me/username/42  or  https://t.me/username
    m = re.match(r"https?://t\.me/([^/?\s]+)(?:/(\d+))?", ref)
    if m:
        return "@" + m.group(1), int(m.group(2)) if m.group(2) else None

    if ref.startswith("@"):
        return ref, None

    try:
        return int(ref), None
    except ValueError:
        return ref, None


def build_proxy(proxy_config: Optional[dict]):
    """
    Build Telethon proxy args.  Returns (proxy, connection_class).
    connection_class is None for SOCKS/HTTP, set for MTProto proxy.
    """
    if not proxy_config:
        return None, None

    ptype = proxy_config.get("type", "socks5").lower()
    host = proxy_config["host"]
    port = int(proxy_config["port"])

    if ptype == "mtproto":
        from telethon.network.connection.tcpmtproxy import (
            ConnectionTcpMTProxyRandomizedIntermediate,
        )
        secret = proxy_config.get("secret", "")
        return (host, port, secret), ConnectionTcpMTProxyRandomizedIntermediate

    try:
        import socks
    except ImportError:
        raise ImportError(
            "SOCKS/HTTP proxy requires PySocks: pip install pysocks"
        )

    stype = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http": socks.HTTP,
    }.get(ptype, socks.SOCKS5)
    username = proxy_config.get("username") or proxy_config.get("user") or None
    password = proxy_config.get("password") or None
    return (stype, host, port, True, username, password), None


def _entity_type(entity) -> str:
    if isinstance(entity, User):
        return "bot" if entity.bot else "user"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "supergroup" if entity.megagroup else "channel"
    return "unknown"


def _sender_name(sender) -> str:
    if sender is None:
        return ""
    if isinstance(sender, User):
        parts = [p for p in [sender.first_name, sender.last_name] if p]
        return " ".join(parts) or str(sender.id)
    return getattr(sender, "title", "") or str(getattr(sender, "id", ""))


def _media_type(media) -> Optional[str]:
    if media is None or isinstance(media, MessageMediaWebPage):
        return None
    if isinstance(media, MessageMediaPhoto):
        return "photo"
    if isinstance(media, MessageMediaDocument):
        return "document"
    return "media"


def _fmt_msg(msg) -> Dict:
    return {
        "id": msg.id,
        "date": msg.date.strftime("%Y-%m-%dT%H:%M:%SZ") if msg.date else None,
        "sender": _sender_name(msg.sender),
        "sender_id": msg.sender_id,
        "text": msg.text or "",
        "media": _media_type(msg.media),
        "reply_to_id": (
            msg.reply_to.reply_to_msg_id if getattr(msg, "reply_to", None) else None
        ),
        "forwarded_from": getattr(getattr(msg, "fwd_from", None), "from_name", None),
    }


def _peer_matches(peer, entity) -> bool:
    if isinstance(peer, InputPeerUser) and isinstance(entity, User):
        return peer.user_id == entity.id
    if isinstance(peer, InputPeerChat) and isinstance(entity, Chat):
        return peer.chat_id == entity.id
    if isinstance(peer, InputPeerChannel) and isinstance(entity, Channel):
        return peer.channel_id == entity.id
    return False


def _dialog_in_filter(dialog, f: DialogFilter) -> bool:
    """Return True if *dialog* belongs to folder filter *f*."""
    entity = dialog.entity

    for peer in getattr(f, "exclude_peers", []):
        if _peer_matches(peer, entity):
            return False

    included = list(getattr(f, "pinned_peers", [])) + list(getattr(f, "include_peers", []))
    for peer in included:
        if _peer_matches(peer, entity):
            return True

    # Boolean type flags (for folders that include whole categories)
    if isinstance(entity, User):
        if entity.bot and getattr(f, "bots", False):
            return True
        if not entity.bot:
            if getattr(f, "contacts", False) and getattr(entity, "contact", False):
                return True
            if getattr(f, "non_contacts", False) and not getattr(entity, "contact", False):
                return True
    elif isinstance(entity, Chat):
        if getattr(f, "groups", False):
            return True
    elif isinstance(entity, Channel):
        if entity.megagroup and getattr(f, "groups", False):
            return True
        if not entity.megagroup and getattr(f, "broadcasts", False):
            return True

    return False


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TelegramReader:
    def __init__(self, config):
        self._config = config
        self._client: Optional[TelegramClient] = None
        self._folder_filters = None   # cached after first load
        self._dialogs_cache = None    # cached for session lifetime
        self._enc_session_path: Optional[str] = None  # set when encrypted session is used

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        import os
        from . import session as _session

        session_dir = os.path.dirname(self._config.session_file)
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)

        proxy, conn_cls = build_proxy(self._config.proxy)
        kwargs: Dict = {}
        if proxy:
            kwargs["proxy"] = proxy
        if conn_cls:
            kwargs["connection"] = conn_cls

        if _session.pin_is_set():
            from telethon.sessions import StringSession
            enc = _session.enc_path(self._config.session_file)
            session_string = _session.load(enc, _session.get_pin())
            telethon_session = StringSession(session_string)
            self._enc_session_path = enc
        else:
            telethon_session = self._config.session_file
            self._enc_session_path = None

        self._client = TelegramClient(
            telethon_session,
            self._config.api_id,
            self._config.api_hash,
            **kwargs,
        )
        await self._client.connect()

        if not await self._client.is_user_authorized():
            await self._client.disconnect()
            raise RuntimeError(
                "Not authorized. Run  python -m telemcp.auth --config <config.json>  first."
            )

    async def disconnect(self):
        if self._client:
            if self._enc_session_path:
                from . import session as _session
                from telethon.sessions import StringSession
                session_string = StringSession.save(self._client.session)
                _session.save(session_string, self._enc_session_path, _session.get_pin())
            await self._client.disconnect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_folders(self) -> List[Dict]:
        """Return all Telegram folder filters with id and name."""
        filters = await self._load_filters()
        result = []
        for f in filters:
            if isinstance(f, DialogFilterDefault):
                result.append({"id": 0, "name": "All Chats"})
            elif isinstance(f, DialogFilter):
                result.append({"id": f.id, "name": f.title.text if hasattr(f.title, 'text') else str(f.title)})
        return result

    async def get_dialogs(
        self,
        folder_id: Optional[int] = None,
        whitelist=None,
    ) -> List[Dict]:
        """
        Return dialogs.  If whitelist is configured, only whitelisted dialogs
        are returned.  If folder_id is given, further limit to that folder.
        When whitelist is empty, all dialogs are returned (for initial setup).
        """
        dialogs = await self._all_dialogs()

        if folder_id is not None:
            allowed_ids = await self._entity_ids_in_folder(folder_id)
            dialogs = [d for d in dialogs if d.entity.id in allowed_ids]

        if whitelist and whitelist.is_configured():
            dialogs = [d for d in dialogs if await self._is_allowed(d, whitelist)]

        return [self._fmt_dialog(d) for d in dialogs]

    async def get_messages(
        self,
        chat_ref: str,
        limit: int = 50,
        unread_only: bool = False,
        since_hours: Optional[float] = None,
        since_message_id: Optional[int] = None,
        whitelist=None,
    ) -> List[Dict]:
        """Fetch messages from a chat.  Never marks them as read."""
        if whitelist and not whitelist.is_configured():
            raise PermissionError(
                "Whitelist is empty. Configure whitelist in config.json first. "
                "Use tg_list_folders / tg_list_dialogs to discover IDs."
            )

        chat_id, _ = parse_chat_ref(chat_ref)
        entity = await self._client.get_entity(chat_id)

        if whitelist and whitelist.is_configured():
            dialogs = await self._all_dialogs()
            dialog = next((d for d in dialogs if d.entity.id == entity.id), None)
            if not dialog or not await self._is_allowed(dialog, whitelist):
                raise PermissionError(
                    f"Chat {chat_ref!r} is not in the whitelist."
                )

        fetch_limit = min(limit, 200)

        if unread_only:
            dialogs = await self._all_dialogs()
            dialog = next((d for d in dialogs if d.entity.id == entity.id), None)
            if not dialog or dialog.unread_count == 0:
                return []
            fetch_limit = min(dialog.unread_count, fetch_limit)

        kwargs: Dict = {"limit": fetch_limit}
        if since_message_id:
            kwargs["min_id"] = since_message_id

        since_dt: Optional[datetime] = None
        if since_hours:
            since_dt = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        messages: List[Dict] = []
        async for msg in self._client.iter_messages(entity, **kwargs):
            if since_dt and msg.date:
                msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                if msg_date < since_dt:
                    break
            if msg.text or msg.media:
                messages.append(_fmt_msg(msg))

        return messages

    async def get_unread_summary(
        self,
        folder_id: Optional[int] = None,
        max_per_chat: int = 20,
        whitelist=None,
    ) -> Dict:
        """
        Return a digest: for each chat with unread messages, include the last
        N unread messages.  Does not mark anything as read.
        """
        if whitelist and not whitelist.is_configured():
            raise PermissionError(
                "Whitelist is empty. Configure whitelist in config.json first. "
                "Use tg_list_folders / tg_list_dialogs to discover IDs."
            )

        dialogs = await self._all_dialogs()

        if folder_id is not None:
            allowed_ids = await self._entity_ids_in_folder(folder_id)
            dialogs = [d for d in dialogs if d.entity.id in allowed_ids]

        if whitelist and whitelist.is_configured():
            dialogs = [d for d in dialogs if await self._is_allowed(d, whitelist)]

        unread = [d for d in dialogs if d.unread_count > 0]

        chats = []
        for dialog in unread:
            count = min(dialog.unread_count, max_per_chat)
            msgs: List[Dict] = []
            async for msg in self._client.iter_messages(dialog.entity, limit=count):
                if msg.text or msg.media:
                    msgs.append(_fmt_msg(msg))
            chats.append({
                "chat_id": dialog.entity.id,
                "chat_name": dialog.name,
                "type": _entity_type(dialog.entity),
                "unread_count": dialog.unread_count,
                "messages": msgs,
            })

        folder_name: Optional[str] = None
        if folder_id is not None:
            for f in await self._load_filters():
                if isinstance(f, DialogFilter) and f.id == folder_id:
                    folder_name = f.title.text if hasattr(f.title, 'text') else str(f.title)
                    break

        return {
            "folder": folder_name,
            "chats_with_unread": len(unread),
            "chats": chats,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_filters(self):
        if self._folder_filters is None:
            result = await self._client(GetDialogFiltersRequest())
            self._folder_filters = result.filters
        return self._folder_filters

    async def _all_dialogs(self):
        """Fetch all dialogs once, cache for the session."""
        if self._dialogs_cache is None:
            self._dialogs_cache = await self._client.get_dialogs(limit=None)
        return self._dialogs_cache

    async def _entity_ids_in_folder(self, folder_id: int) -> set:
        filters = await self._load_filters()
        for f in filters:
            if isinstance(f, DialogFilter) and f.id == folder_id:
                dialogs = await self._all_dialogs()
                return {d.entity.id for d in dialogs if _dialog_in_filter(d, f)}
        return set()

    async def _is_allowed(self, dialog, whitelist) -> bool:
        entity = dialog.entity
        username = getattr(entity, "username", None)

        if whitelist.allows_direct(entity.id, username):
            return True

        if whitelist.folder_ids:
            filters = await self._load_filters()
            for f in filters:
                if isinstance(f, DialogFilter) and whitelist.allows_folder(f.id):
                    if _dialog_in_filter(dialog, f):
                        return True

        return False

    def _fmt_dialog(self, dialog) -> Dict:
        entity = dialog.entity
        last_date = None
        if dialog.message and getattr(dialog.message, "date", None):
            last_date = dialog.message.date.strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "id": entity.id,
            "name": dialog.name,
            "type": _entity_type(entity),
            "unread_count": dialog.unread_count,
            "last_message_date": last_date,
            "username": getattr(entity, "username", None),
        }
