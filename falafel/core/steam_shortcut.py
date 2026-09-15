"""Adding falafel to Steam's library as a "Non-Steam Game" shortcut.

Points the shortcut at falafel's own launcher (not at Battle.net.exe
directly) so Steam just runs a native Linux executable and never applies
its own Proton translation — which matters, because if Exe pointed at the
Windows exe, Steam would create and use a *separate* Proton prefix under
steamapps/compatdata/ instead of reusing the umu-managed prefix this whole
project is built around.

shortcuts.vdf is a shared file — the user may already have other non-Steam
games in it (verified against a real one with several unrelated entries
during development) — so this always parses the whole file with steam_vdf,
edits only the one entry that matches by Exe path (idempotent: rerunning
updates rather than duplicates), and writes a timestamped backup before
touching the file.
"""

from __future__ import annotations

import shutil
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import steam_vdf

# Fields Steam itself writes for a shortcut entry; values are placeholders
# overwritten (or left as-is on update, for the ones marked "sticky") below.
_DEFAULT_ENTRY_FIELDS: dict[str, str | int] = {
    "appid": 0,
    "AppName": "",
    "Exe": "",
    "StartDir": "",
    "icon": "",
    "ShortcutPath": "",
    "LaunchOptions": "",
    "IsHidden": 0,
    "AllowDesktopConfig": 1,
    "AllowOverlay": 1,
    "OpenVR": 0,
    "Devkit": 0,
    "DevkitGameID": "",
    "DevkitOverrideAppID": 0,
    "LastPlayTime": 0,
    "FlatpakAppID": "",
    "tags": {},
}


def compute_legacy_shortcut_id(exe: str, app_name: str) -> int:
    """Valve's CRC32-based id for a non-Steam shortcut's artwork files.

    Community-reverse-engineered (used by most third-party Steam library art
    tools); not guaranteed by Valve, but matches what Steam itself derives
    from the same (Exe, AppName) pair for grid image filenames.
    """
    key = (exe + app_name).encode("utf-8")
    return (zlib.crc32(key) | 0x80000000) & 0xFFFFFFFF


def find_userdata_config_dir(steam_root: Path | None = None) -> Path:
    """Find the active user's Steam userdata config/ dir.

    If more than one userdata/<id>/ exists (multiple accounts having ever
    logged in on this machine), picks whichever has the most recently
    modified config dir as a best-effort guess at "the current user".
    """
    steam_root = steam_root or (Path.home() / ".local" / "share" / "Steam")
    userdata = steam_root / "userdata"
    candidates = []
    if userdata.is_dir():
        candidates = [
            p / "config" for p in userdata.iterdir() if p.is_dir() and (p / "config").is_dir()
        ]
    if not candidates:
        raise FileNotFoundError(f"no Steam userdata config directory found under {userdata}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


@dataclass(frozen=True)
class AddShortcutResult:
    shortcuts_path: Path
    backup_path: Path | None
    appid: int
    was_update: bool


def add_shortcut(
    *,
    exe: str,
    app_name: str,
    start_dir: str,
    launch_options: str = "",
    icon: str = "",
    steam_root: Path | None = None,
) -> AddShortcutResult:
    """Add (or update, if an entry for this Exe already exists) a Steam shortcut.

    Idempotent by Exe path: safe to call again (e.g. to change the name or
    icon later) without creating a duplicate entry.
    """
    config_dir = find_userdata_config_dir(steam_root)
    shortcuts_path = config_dir / "shortcuts.vdf"

    if shortcuts_path.exists():
        root = steam_vdf.loads(shortcuts_path.read_bytes())
    else:
        root = {}
    shortcuts = root.setdefault("shortcuts", {})

    exe_quoted = f'"{exe}"'
    appid = compute_legacy_shortcut_id(exe, app_name)

    existing_index = next(
        (idx for idx, entry in shortcuts.items() if entry.get("Exe") == exe_quoted),
        None,
    )
    was_update = existing_index is not None
    index = existing_index if was_update else str(len(shortcuts))

    entry = dict(shortcuts.get(index, _DEFAULT_ENTRY_FIELDS))
    entry["appid"] = appid
    entry["AppName"] = app_name
    entry["Exe"] = exe_quoted
    entry["StartDir"] = start_dir
    entry["LaunchOptions"] = launch_options
    if icon:
        entry["icon"] = icon
    entry.setdefault("tags", {})
    shortcuts[index] = entry

    backup_path = None
    if shortcuts_path.exists():
        backup_path = shortcuts_path.with_name(
            f"shortcuts.vdf.bak.{time.strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(shortcuts_path, backup_path)

    shortcuts_path.write_bytes(steam_vdf.dumps(root))

    # Defense in depth: re-read what we just wrote and confirm it parses
    # back to exactly what we intended, before ever telling the caller it
    # succeeded.
    verify = steam_vdf.loads(shortcuts_path.read_bytes())
    if verify["shortcuts"][index]["AppName"] != app_name:
        raise RuntimeError("shortcuts.vdf write did not verify correctly after writing")

    if icon:
        _write_grid_art(config_dir, appid, Path(icon))

    return AddShortcutResult(
        shortcuts_path=shortcuts_path,
        backup_path=backup_path,
        appid=appid,
        was_update=was_update,
    )


def remove_shortcut(exe: str, *, steam_root: Path | None = None) -> Path | None:
    """Remove the shortcut entry matching this Exe path, if any.

    Renumbers the remaining entries to stay sequential ("0", "1", ...),
    matching the shape Steam's own UI produces. Writes a timestamped backup
    first, same as add_shortcut. Returns the backup path if an entry was
    actually removed, or None if there was nothing to remove (no
    shortcuts.vdf, or no entry with this Exe).
    """
    config_dir = find_userdata_config_dir(steam_root)
    shortcuts_path = config_dir / "shortcuts.vdf"
    if not shortcuts_path.exists():
        return None

    root = steam_vdf.loads(shortcuts_path.read_bytes())
    shortcuts = root.get("shortcuts", {})
    exe_quoted = f'"{exe}"'
    remaining = [entry for entry in shortcuts.values() if entry.get("Exe") != exe_quoted]
    if len(remaining) == len(shortcuts):
        return None

    root["shortcuts"] = {str(i): entry for i, entry in enumerate(remaining)}

    backup_path = shortcuts_path.with_name(f"shortcuts.vdf.bak.{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(shortcuts_path, backup_path)
    shortcuts_path.write_bytes(steam_vdf.dumps(root))

    verify = steam_vdf.loads(shortcuts_path.read_bytes())
    if any(entry.get("Exe") == exe_quoted for entry in verify.get("shortcuts", {}).values()):
        raise RuntimeError("shortcuts.vdf write did not verify correctly after removing entry")

    return backup_path


def _write_grid_art(config_dir: Path, appid: int, icon_path: Path) -> None:
    """Best-effort: copy the given image into Steam's grid art slots.

    Written under both the legacy 32-bit id and the 64-bit grid id, since
    which one a given Steam version reads for the library tile isn't
    reliably documented; an unrecognized filename is simply ignored, so
    writing both is harmless. If this doesn't pick up automatically, the
    user can always set it manually via right-click > Manage in Steam.
    """
    if not icon_path.is_file():
        return
    suffix = icon_path.suffix or ".png"
    grid_dir = config_dir / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    for ident in (appid, (appid << 32) | 0x02000000):  # legacy 32-bit, then 64-bit grid id
        for name in (f"{ident}{suffix}", f"{ident}_icon{suffix}"):
            shutil.copy2(icon_path, grid_dir / name)
