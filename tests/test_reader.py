"""Tests for fcookex.reader."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fcookex.reader import Cookie, search_cookies


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path, rows: list[tuple]) -> Path:
    """Create a minimal moz_cookies SQLite database with the given rows.

    Each row must be: (host, name, value, path, expiry, isSecure, isHttpOnly, sameSite)
    """
    db = tmp_path / "cookies.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT, name TEXT, value TEXT, path TEXT,
            expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER
        )"""
    )
    conn.executemany(
        "INSERT INTO moz_cookies (host, name, value, path, expiry, isSecure, isHttpOnly, sameSite) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


_SAMPLE_ROWS = [
    (".example.com", "session", "abc123", "/", 9999999999, 1, 1, 0),
    (".example.com", "tracker", "xyz", "/analytics", 9999999999, 0, 0, 0),
    (".other.org", "auth", "secret", "/", 9999999999, 1, 1, 0),
    (".github.com", "logged_in", "yes", "/", 9999999999, 1, 0, 2),
]


# ---------------------------------------------------------------------------
# search_cookies
# ---------------------------------------------------------------------------


def test_search_by_host(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "example")
    hosts = {c.host for c in results}
    assert hosts == {".example.com"}
    assert len(results) == 2


def test_search_by_name(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "session")
    assert len(results) == 1
    assert results[0].name == "session"


def test_search_by_value(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "abc123")
    assert len(results) == 1
    assert results[0].value == "abc123"


def test_search_case_insensitive(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "EXAMPLE")
    assert len(results) == 2


def test_search_no_results(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "nonexistent_xyz_999")
    assert results == []


def test_search_returns_cookie_dataclass(tmp_path):
    db = _make_db(tmp_path, _SAMPLE_ROWS)
    results = search_cookies(db, "github")
    assert len(results) == 1
    c = results[0]
    assert isinstance(c, Cookie)
    assert c.host == ".github.com"
    assert c.name == "logged_in"
    assert c.is_secure is True
    assert c.same_site == 2


def test_search_empty_db(tmp_path):
    db = _make_db(tmp_path, [])
    assert search_cookies(db, "anything") == []
