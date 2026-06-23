"""Tests for telemcp.config."""
import json
import os
import pytest

from telemcp.config import (
    Config,
    TELEGRAM_DESKTOP_API_ID,
    TELEGRAM_DESKTOP_API_HASH,
)

VALID_DATA = {
    "api_id": 12345,
    "api_hash": "abc123",
    "session_file": "/tmp/test_session",
    "whitelist": {"folders": [2], "groups": [-100123], "accounts": []},
    "proxy": None,
}


# ---------------------------------------------------------------------------
# Config.__init__
# ---------------------------------------------------------------------------

class TestConfigInit:
    def test_valid_credentials(self):
        cfg = Config(VALID_DATA)
        assert cfg.api_id == 12345
        assert cfg.api_hash == "abc123"

    def test_session_file_expansion(self):
        data = {**VALID_DATA, "session_file": "~/.telemcp/session"}
        cfg = Config(data)
        assert "~" not in cfg.session_file
        assert cfg.session_file.endswith("/.telemcp/session")

    def test_session_file_default(self):
        data = {k: v for k, v in VALID_DATA.items() if k != "session_file"}
        cfg = Config(data)
        assert cfg.session_file.endswith("/.telemcp/session")

    def test_whitelist_parsed(self):
        cfg = Config(VALID_DATA)
        assert cfg.whitelist["folders"] == [2]
        assert cfg.whitelist["groups"] == [-100123]
        assert cfg.whitelist["accounts"] == []

    def test_proxy_none(self):
        cfg = Config(VALID_DATA)
        assert cfg.proxy is None

    def test_proxy_present(self):
        data = {**VALID_DATA, "proxy": {"type": "socks5", "host": "127.0.0.1", "port": 1080}}
        cfg = Config(data)
        assert cfg.proxy["host"] == "127.0.0.1"

    def test_fallback_credentials_when_missing(self, capsys):
        data = {k: v for k, v in VALID_DATA.items() if k not in ("api_id", "api_hash")}
        cfg = Config(data)
        assert cfg.api_id == TELEGRAM_DESKTOP_API_ID
        assert cfg.api_hash == TELEGRAM_DESKTOP_API_HASH
        assert "WARNING" in capsys.readouterr().err

    def test_fallback_credentials_when_null(self, capsys):
        data = {**VALID_DATA, "api_id": None, "api_hash": None}
        cfg = Config(data)
        assert cfg.api_id == TELEGRAM_DESKTOP_API_ID
        capsys.readouterr()  # consume output


# ---------------------------------------------------------------------------
# Config.load — path resolution
# ---------------------------------------------------------------------------

def _write_config(path, data=None):
    path.write_text(json.dumps(data or VALID_DATA), encoding="utf-8")


class TestConfigLoad:
    def test_absolute_path(self, tmp_path):
        f = tmp_path / "config.json"
        _write_config(f)
        cfg = Config.load(str(f))
        assert cfg.api_id == 12345

    def test_relative_path_found_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "config.json"
        _write_config(f)
        cfg = Config.load("config.json")
        assert cfg.api_id == 12345

    def test_relative_path_fallback_to_telemcp_dir(self, tmp_path, monkeypatch):
        # CWD has no config, but ~/.telemcp/ does
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.chdir(empty)

        fake_home = tmp_path / "home"
        telemcp_dir = fake_home / ".telemcp"
        telemcp_dir.mkdir(parents=True)
        _write_config(telemcp_dir / "config.json")

        monkeypatch.setattr(os.path, "expanduser",
                            lambda p: str(fake_home / p.lstrip("~/")) if p.startswith("~") else p)

        cfg = Config.load("config.json")
        assert cfg.api_id == 12345

    def test_missing_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            Config.load("nonexistent.json")

    def test_invalid_json_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
        with pytest.raises(SystemExit):
            Config.load("bad.json")
