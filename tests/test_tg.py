"""Tests for pure helper functions in telemcp.tg (no network required)."""
import pytest

from telemcp.tg import parse_chat_ref, build_proxy


# ---------------------------------------------------------------------------
# parse_chat_ref
# ---------------------------------------------------------------------------

class TestParseChatRef:
    def test_integer_passthrough(self):
        chat_id, msg_id = parse_chat_ref(-1001234567890)
        assert chat_id == -1001234567890
        assert msg_id is None

    def test_numeric_string(self):
        chat_id, msg_id = parse_chat_ref("-1001234567890")
        assert chat_id == -1001234567890
        assert msg_id is None

    def test_at_username(self):
        chat_id, msg_id = parse_chat_ref("@mychannel")
        assert chat_id == "@mychannel"
        assert msg_id is None

    def test_tme_private_channel_with_message(self):
        chat_id, msg_id = parse_chat_ref("https://t.me/c/1668839992/5699")
        assert chat_id == -1001668839992
        assert msg_id == 5699

    def test_tme_private_channel_without_message(self):
        chat_id, msg_id = parse_chat_ref("https://t.me/c/1668839992")
        assert chat_id == -1001668839992
        assert msg_id is None

    def test_tme_public_username(self):
        chat_id, msg_id = parse_chat_ref("https://t.me/durov")
        assert chat_id == "@durov"
        assert msg_id is None

    def test_tme_public_username_with_message(self):
        chat_id, msg_id = parse_chat_ref("https://t.me/durov/42")
        assert chat_id == "@durov"
        assert msg_id == 42

    def test_plain_username_without_at(self):
        # Not starting with @, not a URL, not a number — returned as-is for Telethon
        chat_id, msg_id = parse_chat_ref("somechannel")
        assert chat_id == "somechannel"
        assert msg_id is None

    def test_whitespace_stripped(self):
        chat_id, msg_id = parse_chat_ref("  @chan  ")
        assert chat_id == "@chan"


# ---------------------------------------------------------------------------
# build_proxy
# ---------------------------------------------------------------------------

class TestBuildProxy:
    def test_none_config(self):
        proxy, conn_cls = build_proxy(None)
        assert proxy is None
        assert conn_cls is None

    def test_empty_dict_treated_as_none(self):
        # Falsy proxy config
        proxy, conn_cls = build_proxy({})
        # build_proxy checks `if not proxy_config` — empty dict is falsy
        assert proxy is None
        assert conn_cls is None

    def test_socks5_proxy(self):
        cfg = {"type": "socks5", "host": "127.0.0.1", "port": 1080}
        proxy, conn_cls = build_proxy(cfg)
        assert proxy is not None
        assert conn_cls is None   # SOCKS5 uses default connection class
        # proxy tuple: (socks_type, host, port, rdns, username, password)
        assert proxy[1] == "127.0.0.1"
        assert proxy[2] == 1080

    def test_socks5_with_credentials(self):
        cfg = {"type": "socks5", "host": "proxy.example.com", "port": 1080,
               "username": "user", "password": "pass"}
        proxy, _ = build_proxy(cfg)
        assert proxy[4] == "user"
        assert proxy[5] == "pass"

    def test_socks5_accepts_user_key(self):
        # Config may use "user" instead of "username"
        cfg = {"type": "socks5", "host": "proxy.example.com", "port": 1080,
               "user": "alice", "password": "secret"}
        proxy, _ = build_proxy(cfg)
        assert proxy[4] == "alice"

    def test_port_coerced_to_int(self):
        cfg = {"type": "socks5", "host": "127.0.0.1", "port": "1080"}
        proxy, _ = build_proxy(cfg)
        assert proxy[2] == 1080

    def test_mtproto_proxy(self):
        cfg = {"type": "mtproto", "host": "proxy.example.com", "port": 443,
               "secret": "dd1234abcdef"}
        proxy, conn_cls = build_proxy(cfg)
        assert proxy == ("proxy.example.com", 443, "dd1234abcdef")
        assert conn_cls is not None
