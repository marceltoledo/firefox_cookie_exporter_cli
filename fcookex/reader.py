"""Read and search Firefox cookies from a moz_cookies SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cookie:
    host: str
    name: str
    value: str
    path: str
    expires: int
    is_secure: bool
    is_http_only: bool
    same_site: int


def search_cookies(db: Path, keyword: str) -> list[Cookie]:
    """Return all cookies whose host, name, or value contain *keyword* (case-insensitive)."""
    pattern = f"%{keyword}%"
    conn = sqlite3.connect(str(db))
    try:
        cursor = conn.execute(
            """
            SELECT host, name, value, path, expiry, isSecure, isHttpOnly,
                   COALESCE(sameSite, 0)
            FROM   moz_cookies
            WHERE  host  LIKE ? ESCAPE '\\'
               OR  name  LIKE ? ESCAPE '\\'
               OR  value LIKE ? ESCAPE '\\'
            ORDER BY host, name
            """,
            (pattern, pattern, pattern),
        )
        results: list[Cookie] = []
        for row in cursor:
            host, name, value, path, expiry, is_secure, is_http_only, same_site = row
            results.append(
                Cookie(
                    host=host or "",
                    name=name or "",
                    value=value or "",
                    path=path or "/",
                    expires=expiry or 0,
                    is_secure=bool(is_secure),
                    is_http_only=bool(is_http_only),
                    same_site=int(same_site),
                )
            )
        return results
    finally:
        conn.close()
