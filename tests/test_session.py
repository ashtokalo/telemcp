"""Tests for telemcp.session."""
import os
import sys
import pytest

from telemcp import session as _session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PIN = "test-passphrase-123"
SESSION_STRING = "1BVtsOHIBu..."   # arbitrary string representing a serialised session


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_pin_is_set_true(self, monkeypatch):
        monkeypatch.setenv(_session.ENV_VAR, "secret")
        assert _session.pin_is_set()

    def test_pin_is_set_false(self, monkeypatch):
        monkeypatch.delenv(_session.ENV_VAR, raising=False)
        assert not _session.pin_is_set()

    def test_get_pin_returns_value(self, monkeypatch):
        monkeypatch.setenv(_session.ENV_VAR, "mypin")
        assert _session.get_pin() == "mypin"

    def test_get_pin_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv(_session.ENV_VAR, raising=False)
        assert _session.get_pin() == ""

    def test_enc_path_appends_suffix(self):
        assert _session.enc_path("/home/user/.telemcp/session") == "/home/user/.telemcp/session.enc"


# ---------------------------------------------------------------------------
# Encryption round-trip
# ---------------------------------------------------------------------------

class TestEncryption:
    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        assert os.path.exists(path)

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions not supported on Windows")
    def test_save_sets_permissions(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        mode = oct(os.stat(path).st_mode)[-3:]
        assert mode == "600"

    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        result = _session.load(path, PIN)
        assert result == SESSION_STRING

    def test_different_salts_each_save(self, tmp_path):
        import json
        path1 = str(tmp_path / "s1.enc")
        path2 = str(tmp_path / "s2.enc")
        _session.save(SESSION_STRING, path1, PIN)
        _session.save(SESSION_STRING, path2, PIN)
        d1 = json.loads(open(path1).read())
        d2 = json.loads(open(path2).read())
        assert d1["salt"] != d2["salt"]
        assert d1["data"] != d2["data"]

    def test_long_session_string(self, tmp_path):
        long_string = "A" * 10_000
        path = str(tmp_path / "session.enc")
        _session.save(long_string, path, PIN)
        assert _session.load(path, PIN) == long_string

    def test_wrong_pin_exits(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        with pytest.raises(SystemExit):
            _session.load(path, "wrong-pin")

    def test_file_is_not_plaintext(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        raw = open(path).read()
        assert SESSION_STRING not in raw

    def test_atomic_write_no_tmp_left(self, tmp_path):
        path = str(tmp_path / "session.enc")
        _session.save(SESSION_STRING, path, PIN)
        assert not os.path.exists(path + ".tmp")
