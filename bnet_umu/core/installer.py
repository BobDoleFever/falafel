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
) -> subprocess.CompletedProcess:
    """Run the downloaded Battle.net-Setup.exe under umu, blocking until it exits.

    The user still has to click through the installer UI (and per the known
    Wine workaround, close the login window if it appears rather than logging
    in during setup) since we don't automate the installer's own UI.
    """
    invocation = umu_runner.build_invocation(
        installer_path,
        prefix=prefix,
        proton_path=proton_path,
        gameid="umu-default",
        store="battlenet",
        umu_bin=umu_bin,
    )
    result = umu_runner.run(invocation, background=False)
    assert isinstance(result, subprocess.CompletedProcess)
    return result


def is_game_installed(prefix: Path, game: GameDef) -> bool:
    return find_game_install(prefix, game) is not None
