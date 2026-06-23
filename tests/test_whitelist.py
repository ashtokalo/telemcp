"""Tests for telemcp.whitelist."""
import pytest

from telemcp.whitelist import Whitelist


def wl(folders=(), groups=(), accounts=()):
    return Whitelist({"folders": list(folders), "groups": list(groups), "accounts": list(accounts)})


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_empty_is_not_configured(self):
        assert not wl().is_configured()

    def test_folder_makes_configured(self):
        assert wl(folders=[2]).is_configured()

    def test_group_id_makes_configured(self):
        assert wl(groups=[-1001234567890]).is_configured()

    def test_group_name_makes_configured(self):
        assert wl(groups=["@somechannel"]).is_configured()

    def test_account_makes_configured(self):
        assert wl(accounts=[123456789]).is_configured()


# ---------------------------------------------------------------------------
# allows_folder
# ---------------------------------------------------------------------------

class TestAllowsFolder:
    def test_allowed_folder(self):
        assert wl(folders=[2, 5]).allows_folder(2)

    def test_not_allowed_folder(self):
        assert not wl(folders=[2]).allows_folder(5)

    def test_empty_folders(self):
        assert not wl().allows_folder(2)


# ---------------------------------------------------------------------------
# allows_direct
# ---------------------------------------------------------------------------

class TestAllowsDirect:
    def test_group_by_numeric_id(self):
        w = wl(groups=[-1001234567890])
        assert w.allows_direct(-1001234567890)
        assert not w.allows_direct(-9999)

    def test_group_by_username(self):
        w = wl(groups=["@MyChannel"])
        assert w.allows_direct(999, "MyChannel")
        assert w.allows_direct(999, "@MyChannel")
        assert w.allows_direct(999, "mychannel")   # case-insensitive
        assert not w.allows_direct(999, "other")

    def test_account_by_id(self):
        w = wl(accounts=[123456789])
        assert w.allows_direct(123456789)
        assert not w.allows_direct(987654321)

    def test_account_by_username(self):
        w = wl(accounts=["@friend"])
        assert w.allows_direct(0, "friend")
        assert not w.allows_direct(0, "stranger")

    def test_no_username_provided(self):
        w = wl(groups=["@chan"])
        assert not w.allows_direct(999)   # id not in list, no username given

    def test_empty_whitelist_allows_nothing(self):
        assert not wl().allows_direct(123)
