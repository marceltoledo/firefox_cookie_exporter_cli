"""Firefox profile discovery and DB copy utilities."""

from __future__ import annotations

import shutil
import sys
import tempfile
import warnings
from configparser import ConfigParser
from pathlib import Path


def _default_firefox_base() -> Path:
    if sys.platform == "win32":
        # Standard (non-Store) install — always try this first.
        standard = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox"
        if standard.exists():
            return standard
        # Microsoft Store (MSIX) install — profile is sandboxed under the
        # package directory with a machine-specific ID suffix, e.g.:
        # %LOCALAPPDATA%\Packages\Mozilla.Firefox_<id>\LocalCache\Roaming\Mozilla\Firefox
        packages = Path.home() / "AppData" / "Local" / "Packages"
        matches = sorted(
            packages.glob("Mozilla.Firefox_*/LocalCache/Roaming/Mozilla/Firefox")
        )
        if matches:
            return matches[0]
        # Neither path exists yet; return standard so error messages are useful.
        return standard
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Firefox"
    return Path.home() / ".mozilla" / "firefox"


FIREFOX_BASE = _default_firefox_base()


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
            f"Firefox profiles.ini not found at {FIREFOX_BASE}\n"
            "Possible causes:\n"
            "  1. Firefox is not installed on this system.\n"
            "  2. Firefox has never been opened — launch it once to create the profile.\n"
            "  3. Firefox is open and has locked the profile — close Firefox and retry."
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
