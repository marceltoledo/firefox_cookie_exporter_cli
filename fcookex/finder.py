"""Firefox profile discovery and DB copy utilities."""

from __future__ import annotations

import shutil
import tempfile
import warnings
from configparser import ConfigParser
from pathlib import Path

FIREFOX_BASE = Path.home() / ".mozilla" / "firefox"


class ProfileNotFoundError(Exception):
    pass


def list_profiles() -> dict[str, Path]:
    """Return a mapping of profile name -> cookies.sqlite path.

    Only profiles that actually have a cookies.sqlite file are included.
    """
    ini_path = FIREFOX_BASE / "profiles.ini"
    if not ini_path.exists():
        return {}

    config = ConfigParser()
    config.read(ini_path)

    profiles: dict[str, Path] = {}
    for section in config.sections():
        if not section.startswith("Profile"):
            continue
        if not config.has_option(section, "Path"):
            continue

        name = config.get(section, "Name", fallback=section)
        is_relative = config.getboolean(section, "IsRelative", fallback=True)
        path_value = config.get(section, "Path")

        profile_dir = FIREFOX_BASE / path_value if is_relative else Path(path_value)
        cookies_db = profile_dir / "cookies.sqlite"
        if cookies_db.exists():
            profiles[name] = cookies_db

    return profiles


def _get_default_profile() -> Path:
    """Return the default profile's cookies.sqlite path."""
    ini_path = FIREFOX_BASE / "profiles.ini"
    if not ini_path.exists():
        raise ProfileNotFoundError(
            f"Firefox profiles.ini not found at {FIREFOX_BASE}"
        )

    config = ConfigParser()
    config.read(ini_path)

    # Prefer the path pointed to by an Install* section (Firefox ≥ 67 default)
    for section in config.sections():
        if section.startswith("Install"):
            default_rel = config.get(section, "Default", fallback=None)
            if default_rel:
                profile_dir = FIREFOX_BASE / default_rel
                cookies_db = profile_dir / "cookies.sqlite"
                if cookies_db.exists():
                    return cookies_db

    # Fall back to the Profile* section that has Default=1
    for section in config.sections():
        if not section.startswith("Profile"):
            continue
        if config.getboolean(section, "Default", fallback=False):
            is_relative = config.getboolean(section, "IsRelative", fallback=True)
            path_value = config.get(section, "Path", fallback=None)
            if path_value:
                profile_dir = (
                    FIREFOX_BASE / path_value if is_relative else Path(path_value)
                )
                cookies_db = profile_dir / "cookies.sqlite"
                if cookies_db.exists():
                    return cookies_db

    # Last resort: first profile that exists
    profiles = list_profiles()
    if profiles:
        return next(iter(profiles.values()))

    raise ProfileNotFoundError(
        "No Firefox profile with a cookies.sqlite database was found."
    )


def get_profile_db(profile: str | None) -> Path:
    """Return the path to cookies.sqlite for *profile*.

    If *profile* is None the default Firefox profile is used.
    Raises ProfileNotFoundError when the named profile does not exist.
    """
    if profile is None:
        return _get_default_profile()

    profiles = list_profiles()
    if profile not in profiles:
        valid = sorted(profiles.keys())
        names = ", ".join(valid) if valid else "(none)"
        raise ProfileNotFoundError(
            f"Profile {profile!r} not found. Available profiles: {names}"
        )
    return profiles[profile]


def copy_to_temp(db: Path) -> Path:
    """Return a temporary copy of *db*.

    Warns if Firefox appears to be running (lock file present).
    The caller is responsible for deleting the returned path when done.
    """
    lock_files = [db.parent / "lock", db.parent / "parent.lock"]
    if any(lf.exists() for lf in lock_files):
        warnings.warn(
            "Firefox appears to be running. The exported cookies may be incomplete.",
            UserWarning,
            stacklevel=2,
        )

    tmp = tempfile.NamedTemporaryFile(prefix="fcookex_", suffix=".sqlite", delete=False)
    tmp.close()
    shutil.copy2(db, tmp.name)
    return Path(tmp.name)
