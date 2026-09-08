"""Acquire umu-launcher itself: prefer a system install, otherwise download
the self-contained zipapp release into our own data dir.

umu-launcher is GPL-3.0. We only ever invoke it as a separate subprocess
(never import its code), and this module fetches the official upstream
release artifact directly onto the user's machine rather than vendoring it
in this repo, so there's nothing to bundle/relicense here — same relationship
this project has with Proton/Wine.

The zipapp release asset (`umu-launcher-X.Y.Z-zipapp.tar` on GitHub Releases)
is a plain tar containing `umu/umu-run` (a self-contained Python zipapp
bundling its own dependencies) and a `umu/umu_run.py` symlink to the same
file. We only need the `umu-run` file itself and call it by absolute path.
"""

from __future__ import annotations

import json
import shutil
import stat
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from .prefix import xdg_data_home

RELEASES_API_URL = (
    "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"
)
UMU_RUN_BIN = "umu-run"


def bootstrap_dir() -> Path:
    return xdg_data_home() / "bnet-umu" / "umu"


def bundled_umu_run_path() -> Path:
    return bootstrap_dir() / UMU_RUN_BIN


def find_umu_run() -> Path | None:
    """Prefer a system-installed umu-run (distro package, AUR, etc.) over
    our own bootstrapped copy, so we don't shadow the user's own install."""
    system_path = shutil.which(UMU_RUN_BIN)
    if system_path:
        return Path(system_path)
    bundled = bundled_umu_run_path()
    return bundled if bundled.exists() else None


def latest_zipapp_url() -> tuple[str, str]:
    """Return (version, download_url) for the latest zipapp release asset."""
    with urllib.request.urlopen(RELEASES_API_URL) as response:
        data = json.load(response)
    for asset in data.get("assets", []):
        if asset["name"].endswith("-zipapp.tar"):
            return data["tag_name"], asset["browser_download_url"]
    raise RuntimeError("No zipapp asset found in the latest umu-launcher release")


def extract_zipapp_tar(tar_path: Path, dest_dir: Path) -> Path:
    """Pull the `umu-run` file out of a zipapp tar and install it into
    dest_dir with the executable bit set. Skips the umu_run.py symlink
    since we always call umu-run by its resolved absolute path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tar:
        member = next(
            (m for m in tar.getmembers() if m.isfile() and m.name.endswith("/umu-run")),
            None,
        )
        if member is None:
            raise RuntimeError("umu-run not found inside zipapp tarball")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise RuntimeError("Could not read umu-run from zipapp tarball")

        target = dest_dir / UMU_RUN_BIN
        target.write_bytes(extracted.read())

    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return target


def download_and_install(
    dest_dir: Path | None = None, log: Callable[[str], None] = print
) -> Path:
    dest_dir = dest_dir or bootstrap_dir()
    log("Looking up latest umu-launcher release ...")
    version, url = latest_zipapp_url()
    log(f"Downloading umu-launcher {version} ...")

    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "umu-zipapp.tar"
        with urllib.request.urlopen(url) as response, open(tar_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        umu_run_path = extract_zipapp_tar(tar_path, dest_dir)

    log(f"Installed umu-run to {umu_run_path}")
    return umu_run_path


def ensure_umu_run(log: Callable[[str], None] = print) -> Path:
    """Return a usable umu-run path, downloading it if not already available."""
    existing = find_umu_run()
    if existing is not None:
        return existing
    log("umu-run not found — downloading a self-contained copy ...")
    return download_and_install(log=log)
