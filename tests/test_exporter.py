"""Tests for fcookex.exporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from fcookex.exporter import _HEADER, export
from fcookex.reader import Cookie


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cookie(
    host: str = ".example.com",
    name: str = "session",
    value: str = "abc123",
    path: str = "/",
    expires: int = 9999999999,
    is_secure: bool = True,
    is_http_only: bool = True,
    same_site: int = 0,
) -> Cookie:
    return Cookie(
        host=host,
        name=name,
        value=value,
        path=path,
        expires=expires,
        is_secure=is_secure,
        is_http_only=is_http_only,
        same_site=same_site,
    )


# ---------------------------------------------------------------------------
# Basic export
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path):
    out = export([_cookie()], output_dir=tmp_path)
    assert out.exists()
    assert out.suffix == ".txt"


def test_export_writes_netscape_header(tmp_path):
    out = export([_cookie()], output_dir=tmp_path)
    content = out.read_text()
    assert content.startswith("# Netscape HTTP Cookie File")


def test_export_writes_cookie_line(tmp_path):
    out = export([_cookie()], output_dir=tmp_path)
    lines = [l for l in out.read_text().splitlines() if not l.startswith("#") and l.strip()]
    assert len(lines) == 1
    parts = lines[0].split("\t")
    assert parts[0] == ".example.com"
    assert parts[1] == "TRUE"   # include_subdomains (host starts with '.')
    assert parts[2] == "/"
    assert parts[3] == "TRUE"   # is_secure
    assert parts[4] == "9999999999"
    assert parts[5] == "session"
    assert parts[6] == "abc123"


def test_export_non_subdomain_host(tmp_path):
    out = export([_cookie(host="example.com")], output_dir=tmp_path)
    lines = [l for l in out.read_text().splitlines() if not l.startswith("#") and l.strip()]
    parts = lines[0].split("\t")
    assert parts[1] == "FALSE"


def test_export_insecure_cookie(tmp_path):
    out = export([_cookie(is_secure=False)], output_dir=tmp_path)
    lines = [l for l in out.read_text().splitlines() if not l.startswith("#") and l.strip()]
    parts = lines[0].split("\t")
    assert parts[3] == "FALSE"


# ---------------------------------------------------------------------------
# Filename handling
# ---------------------------------------------------------------------------


def test_export_custom_name_adds_txt(tmp_path):
    out = export([_cookie()], output_dir=tmp_path, output_name="my_cookies")
    assert out.name == "my_cookies.txt"


def test_export_custom_name_keeps_existing_txt(tmp_path):
    out = export([_cookie()], output_dir=tmp_path, output_name="my_cookies.txt")
    assert out.name == "my_cookies.txt"


def test_export_default_name_timestamp_format(tmp_path):
    out = export([_cookie()], output_dir=tmp_path)
    import re
    assert re.match(r"cookies_\d{8}T\d{6}Z\.txt", out.name)


# ---------------------------------------------------------------------------
# Output directory creation
# ---------------------------------------------------------------------------


def test_export_creates_output_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    out = export([_cookie()], output_dir=nested)
    assert nested.is_dir()
    assert out.exists()


# ---------------------------------------------------------------------------
# Append mode
# ---------------------------------------------------------------------------


def test_append_mode_no_duplicate_header(tmp_path):
    c1 = _cookie(name="first")
    c2 = _cookie(name="second")
    out = export([c1], output_dir=tmp_path, output_name="out")
    export([c2], output_dir=tmp_path, output_name="out", append=True)

    content = out.read_text()
    header_count = content.count("# Netscape HTTP Cookie File")
    assert header_count == 1


def test_append_mode_both_cookies_present(tmp_path):
    c1 = _cookie(name="first", value="v1")
    c2 = _cookie(name="second", value="v2")
    out = export([c1], output_dir=tmp_path, output_name="out")
    export([c2], output_dir=tmp_path, output_name="out", append=True)

    content = out.read_text()
    assert "first" in content
    assert "second" in content


def test_append_creates_file_when_absent(tmp_path):
    out = export([_cookie()], output_dir=tmp_path, output_name="new", append=True)
    assert out.exists()
    assert out.read_text().startswith("# Netscape HTTP Cookie File")


def test_overwrite_replaces_content(tmp_path):
    c1 = _cookie(name="old", value="old_val")
    c2 = _cookie(name="new", value="new_val")
    out = export([c1], output_dir=tmp_path, output_name="out")
    export([c2], output_dir=tmp_path, output_name="out", append=False)

    content = out.read_text()
    assert "old" not in content
    assert "new" in content
