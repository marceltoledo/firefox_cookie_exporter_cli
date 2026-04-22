"""Tests for fcookex.finder."""

from __future__ import annotations

import sqlite3
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest

from fcookex.finder import (
    ProfileNotFoundError,
    _default_firefox_base,
    copy_to_temp,
    get_profile_db,
    list_profiles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile_tree(base: Path, profiles: dict[str, bool]) -> Path:
    """Create a minimal Firefox profile tree under *base*.

    *profiles* maps profile name -> is_default.
    Returns the path to profiles.ini.
    """
    ini = base / "profiles.ini"
    config = ConfigParser()

    for idx, (name, is_default) in enumerate(profiles.items()):
        rel_path = f"{name}.default"
        profile_dir = base / rel_path
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Create a minimal (empty) cookies.sqlite
        conn = sqlite3.connect(str(profile_dir / "cookies.sqlite"))
        conn.execute(
            """CREATE TABLE IF NOT EXISTS moz_cookies (
                id INTEGER PRIMARY KEY,
                host TEXT, name TEXT, value TEXT, path TEXT,
                expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER,
                sameSite INTEGER DEFAULT 0
            )"""
        )
        conn.commit()
        conn.close()

        section = f"Profile{idx}"
        config[section] = {
            "Name": name,
            "IsRelative": "1",
            "Path": rel_path,
        }
        if is_default:
            config[section]["Default"] = "1"

    with open(ini, "w") as fh:
        config.write(fh)

    return ini


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


def test_list_profiles_returns_all(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, {"alice": False, "bob": True})

    profiles = list_profiles()
    assert set(profiles.keys()) == {"alice", "bob"}
    for path in profiles.values():
        assert path.name == "cookies.sqlite"
        assert path.exists()


def test_list_profiles_empty_when_no_ini(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    assert list_profiles() == {}


# ---------------------------------------------------------------------------
# get_profile_db — default
# ---------------------------------------------------------------------------


def test_get_profile_db_default_returns_default_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, {"work": False, "personal": True})

    db = get_profile_db(None)
    assert db.exists()
    assert "personal" in str(db)


def test_get_profile_db_named(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, {"work": False, "personal": True})

    db = get_profile_db("work")
    assert db.exists()
    assert "work" in str(db)


def test_get_profile_db_unknown_name_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, {"personal": True})

    with pytest.raises(ProfileNotFoundError, match="work"):
        get_profile_db("work")


def test_get_profile_db_no_ini_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)

    with pytest.raises(ProfileNotFoundError):
        get_profile_db(None)


# ---------------------------------------------------------------------------
# copy_to_temp
# ---------------------------------------------------------------------------


def test_copy_to_temp_creates_readable_copy(tmp_path):
    original = tmp_path / "cookies.sqlite"
    conn = sqlite3.connect(str(original))
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('hello')")
    conn.commit()
    conn.close()

    copy = copy_to_temp(original)
    try:
        assert copy.exists()
        assert copy != original
        conn2 = sqlite3.connect(str(copy))
        row = conn2.execute("SELECT v FROM t").fetchone()
        conn2.close()
        assert row == ("hello",)
    finally:
        copy.unlink(missing_ok=True)


def test_copy_to_temp_warns_when_lock_present(tmp_path):
    db = tmp_path / "cookies.sqlite"
    db.touch()
    (tmp_path / "lock").touch()

    with pytest.warns(UserWarning, match="Firefox appears to be running"):
        copy = copy_to_temp(db)
    copy.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _default_firefox_base — platform path structure
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific path check")
def test_default_firefox_base_windows():
    base = _default_firefox_base()
    parts = base.parts
    assert "AppData" in parts
    assert "Roaming" in parts
    assert "Mozilla" in parts
    assert "Firefox" in parts


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific path check")
def test_default_firefox_base_macos():
    base = _default_firefox_base()
    assert "Library" in base.parts
    assert "Application Support" in base.parts
    assert "Firefox" in base.parts


@pytest.mark.skipif(sys.platform == "win32" or sys.platform == "darwin",
                    reason="Linux-specific path check")
def test_default_firefox_base_linux():
    base = _default_firefox_base()
    assert ".mozilla" in base.parts
    assert "firefox" in base.parts


# ---------------------------------------------------------------------------
# ProfileNotFoundError message — actionable guidance
# ---------------------------------------------------------------------------


def test_profiles_ini_missing_error_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)

    with pytest.raises(ProfileNotFoundError) as exc_info:
        get_profile_db(None)

    message = str(exc_info.value)
    assert str(tmp_path) in message
    assert "not installed" in message or "never been opened" in message or "close Firefox" in message
