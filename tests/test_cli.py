"""Tests for the --all flag in fcookex.cli."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fcookex.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile_tree(base: Path, cookies: list[tuple]) -> None:
    """Create a minimal Firefox profile tree with a single default profile."""
    from configparser import ConfigParser

    profile_dir = base / "default.default"
    profile_dir.mkdir(parents=True, exist_ok=True)

    db = profile_dir / "cookies.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT, name TEXT, value TEXT, path TEXT,
            expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER,
            sameSite INTEGER DEFAULT 0
        )"""
    )
    conn.executemany(
        "INSERT INTO moz_cookies (host, name, value, path, expiry, isSecure, isHttpOnly, sameSite) "
        "VALUES (?,?,?,?,?,?,?,?)",
        cookies,
    )
    conn.commit()
    conn.close()

    ini = base / "profiles.ini"
    config = ConfigParser()
    config["Profile0"] = {
        "Name": "default",
        "IsRelative": "1",
        "Path": "default.default",
        "Default": "1",
    }
    with open(ini, "w") as fh:
        config.write(fh)


_YOUTUBE_COOKIES = [
    (".youtube.com", "SID", "sid_value", "/", 9999999999, 1, 1, 0),
    (".youtube.com", "HSID", "hsid_value", "/", 9999999999, 1, 1, 0),
    (".youtube.com", "LOGIN_INFO", "login_value", "/", 9999999999, 1, 1, 0),
]


# ---------------------------------------------------------------------------
# AC-01: --all exports all matched cookies without interactive checkbox
# ---------------------------------------------------------------------------


def test_all_flag_exports_without_prompt(tmp_path, monkeypatch):
    """--all skips the inquirer prompt and exports every matched cookie."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer") as mock_inquirer:
        result = runner.invoke(app, ["--search", "youtube", "--all"])

    assert result.exit_code == 0, result.output
    mock_inquirer.checkbox.assert_not_called()

    exported_files = list(export_dir.glob("*.txt"))
    assert len(exported_files) == 1

    content = exported_files[0].read_text()
    assert "SID" in content
    assert "HSID" in content
    assert "LOGIN_INFO" in content


# ---------------------------------------------------------------------------
# AC-02: interactive flow is unchanged when --all is absent
# ---------------------------------------------------------------------------


def test_without_all_flag_calls_checkbox(tmp_path, monkeypatch):
    """Without --all, the inquirer checkbox is still invoked."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer") as mock_inquirer:
        # Return the first choice from whatever choices the CLI builds, so that
        # _resolve_real can find it by identity in the masked-cookie index.
        def _fake_checkbox(**kwargs):
            from unittest.mock import MagicMock
            choices = kwargs.get("choices", [])
            m = MagicMock()
            m.execute.return_value = [choices[0]["value"]] if choices else []
            return m
        mock_inquirer.checkbox.side_effect = _fake_checkbox
        result = runner.invoke(app, ["--search", "youtube"])

    assert result.exit_code == 0, result.output
    mock_inquirer.checkbox.assert_called_once()


# ---------------------------------------------------------------------------
# AC-03: --all combined with --output produces a predictably named file
# ---------------------------------------------------------------------------


def test_all_flag_with_output_name(tmp_path, monkeypatch):
    """--all --output produces export/<name>.txt with a valid Netscape header."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer"):
        result = runner.invoke(app, ["--search", "youtube", "--all", "--output", "youtube-cookies"])

    assert result.exit_code == 0, result.output
    out_file = export_dir / "youtube-cookies.txt"
    assert out_file.exists()
    assert out_file.read_text().startswith("# Netscape HTTP Cookie File")


# ---------------------------------------------------------------------------
# AC-04: --all with zero results exits cleanly, no file written
# ---------------------------------------------------------------------------


def test_all_flag_no_results_exits_cleanly(tmp_path, monkeypatch):
    """--all with no matching cookies exits with a warning and writes no file."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer"):
        result = runner.invoke(app, ["--search", "nonexistent.domain.xyz", "--all"])

    assert result.exit_code == 0
    assert "No cookies found" in result.output
    assert not export_dir.exists() or list(export_dir.glob("*.txt")) == []


# ---------------------------------------------------------------------------
# AC-05: --show-values warning is suppressed when --all is set
# ---------------------------------------------------------------------------


def test_all_flag_suppresses_show_values_warning(tmp_path, monkeypatch):
    """--all suppresses the masked-values notice (no display list is shown)."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer"):
        result = runner.invoke(app, ["--search", "youtube", "--all"])

    assert result.exit_code == 0, result.output
    assert "Cookie values are masked" not in result.output


# ---------------------------------------------------------------------------
# AC-05b: without --all, masked-values notice is still shown
# ---------------------------------------------------------------------------


def test_without_all_flag_shows_masked_notice(tmp_path, monkeypatch):
    """Without --all, the masked-values notice is printed."""
    monkeypatch.setattr("fcookex.finder.FIREFOX_BASE", tmp_path)
    _make_profile_tree(tmp_path, _YOUTUBE_COOKIES)

    export_dir = tmp_path / "export"
    monkeypatch.setattr("fcookex.cli._EXPORT_DIR", export_dir)

    with patch("fcookex.cli.inquirer") as mock_inquirer:
        def _fake_checkbox(**kwargs):
            from unittest.mock import MagicMock
            choices = kwargs.get("choices", [])
            m = MagicMock()
            m.execute.return_value = [choices[0]["value"]] if choices else []
            return m
        mock_inquirer.checkbox.side_effect = _fake_checkbox
        result = runner.invoke(app, ["--search", "youtube"])

    assert "Cookie values are masked" in result.output
