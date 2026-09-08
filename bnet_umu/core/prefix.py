"""Prefix location, game/save discovery, and folder exposure.

Keeps game installs and saves inside the umu/Wine prefix but exposes them at
normal host paths (~/Games/battlenet/...) via symlinks, so the user's file
manager and backup tools don't need to reach into the hidden prefix.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from .games import GameDef

BATTLENET_EXE_GLOB = "Program Files (x86)/Battle.net/Battle.net.exe"


def xdg_data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME")
    if value:
        return Path(value)
    return Path.home() / ".local" / "share"


def xdg_config_home() -> Path:
    value = os.environ.get("XDG_CONFIG_HOME")
    if value:
        return Path(value)
    return Path.home() / ".config"


def default_prefix_path() -> Path:
    return xdg_data_home() / "bnet-umu" / "prefix"


def default_external_root() -> Path:
    return Path.home() / "Games" / "battlenet"


def drive_c(prefix: Path) -> Path:
    return prefix / "drive_c"


def ensure_prefix_parent(prefix: Path) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)


def find_first(prefix: Path, glob_pattern: str) -> Path | None:
    matches = sorted(drive_c(prefix).glob(glob_pattern))
    return matches[0] if matches else None


def find_battlenet_exe(prefix: Path) -> Path | None:
    return find_first(prefix, BATTLENET_EXE_GLOB)


def wait_for_battlenet_exe(
    prefix: Path,
    timeout: float = 300.0,
    poll_interval: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Path | None:
    """Poll the filesystem for Battle.net.exe to appear.

    Used instead of tracking the installer process/window lifecycle, since
    those are less reliable signals than just checking whether the files it
    was supposed to produce actually showed up.
    """
    deadline = clock() + timeout
    while True:
        found = find_battlenet_exe(prefix)
        if found is not None:
            return found
        if clock() >= deadline:
            return None
        sleep_fn(poll_interval)


def find_game_install(prefix: Path, game: GameDef) -> Path | None:
    return find_first(prefix, game.install_glob)


def find_save_dir(prefix: Path, game: GameDef) -> Path | None:
    return find_first(prefix, game.save_glob)


def expose_folder(source: Path, target: Path) -> Path:
    """Symlink target -> source, creating target's parent dir as needed.

    Idempotent: if target is already the correct symlink, does nothing. If
    target exists as something else, raises to avoid clobbering user data.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return target
        raise FileExistsError(
            f"{target} already exists as a symlink to a different location"
        )
    if target.exists():
        raise FileExistsError(f"{target} already exists and is not a symlink")
    target.symlink_to(source, target_is_directory=source.is_dir())
    return target


def expose_game_folders(
    prefix: Path, game: GameDef, external_root: Path | None = None
) -> dict[str, Path | None]:
    """Best-effort exposure of a game's install and save dirs.

    Returns the resulting external paths (or None if the corresponding
    in-prefix directory hasn't appeared yet, e.g. before first install).
    """
    external_root = external_root or default_external_root()
    result: dict[str, Path | None] = {"install": None, "save": None}

    install_dir = find_game_install(prefix, game)
    if install_dir is not None:
        target = external_root / "installs" / game.external_dirname
        result["install"] = expose_folder(install_dir.parent, target)

    save_dir = find_save_dir(prefix, game)
    if save_dir is not None:
        target = external_root / "saves" / game.external_dirname
        result["save"] = expose_folder(save_dir, target)

    return result
