"""Downloading and running the Battle.net installer inside the umu prefix."""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import umu_runner
from .games import GameDef
from .prefix import find_game_install

# Official Blizzard installer download endpoint, also used by Lutris and
# Bottles' Battle.net installers.
BATTLENET_INSTALLER_URL = (
    "https://downloader.battle.net/download/getInstaller?os=win&installer=Battle.net-Setup.exe"
)


def download_installer(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(BATTLENET_INSTALLER_URL) as response, open(
        dest, "wb"
    ) as out_file:
        shutil.copyfileobj(response, out_file)
    return dest


def run_installer(
    installer_path: Path,
    *,
    prefix: Path,
    proton_path: str = "GE-Proton",
    umu_bin: str | Path | None = None,
) -> subprocess.Popen:
    """Launch the downloaded Battle.net-Setup.exe under umu, without waiting
    for it to exit.

    Runs in the background (rather than blocking) so the caller can drive
    its window via `ui_automation` while it's still open, or just leave it
    for the user to click through manually. Either way, the caller should
    treat Battle.net.exe actually appearing on disk (see
    `prefix.wait_for_battlenet_exe`) as the real completion signal rather
    than this process exiting, since Battle.net.exe may keep running under
    the same umu-run session after the installer itself finishes.
    """
    invocation = umu_runner.build_invocation(
        installer_path,
        prefix=prefix,
        proton_path=proton_path,
        gameid="umu-default",
        store="battlenet",
        umu_bin=umu_bin,
    )
    result = umu_runner.run(invocation, background=True)
    assert isinstance(result, subprocess.Popen)
    return result


def is_game_installed(prefix: Path, game: GameDef) -> bool:
    return find_game_install(prefix, game) is not None
