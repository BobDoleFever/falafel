"""Shared Battle.net setup orchestration, used by both the CLI and the GUI.

Takes a `log` callback instead of printing/emitting directly so the GUI can
route lines to a Qt signal and the CLI can just print them.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from . import fixups, installer, prefix, ui_automation, umu_bootstrap


def run_setup(
    prefix_path: Path, proton_path: str, log: Callable[[str], None] = print
) -> bool:
    """Create the prefix, install Battle.net, and apply Wine stability tweaks.

    Returns True if Battle.net.exe is found in the prefix afterwards.
    """
    umu_bin = umu_bootstrap.ensure_umu_run(log=log)

    log(f"Creating prefix at {prefix_path} ...")
    prefix.ensure_prefix_parent(prefix_path)

    with tempfile.TemporaryDirectory() as tmp:
        installer_path = Path(tmp) / "Battle.net-Setup.exe"
        log("Downloading Battle.net installer ...")
        installer.download_installer(installer_path)

        log(
            "Launching installer under umu-run. Complete the install "
            "wizard in the window that opens."
        )
        installer.run_installer(
            installer_path,
            prefix=prefix_path,
            proton_path=proton_path,
            umu_bin=umu_bin,
        )

        log("Waiting for Battle.net to finish installing (up to 5 minutes) ...")
        bnet_exe = prefix.wait_for_battlenet_exe(prefix_path)
        if bnet_exe is not None:
            ui_automation.close_login_window(log=log)

    if bnet_exe is None:
        log(
            "Battle.net.exe not found in prefix after install — setup may "
            "not have completed."
        )
        return False

    # "steamuser" is the Wine username umu/Proton prefixes use by
    # convention; verify against the real prefix if this doesn't match
    # after a first install.
    config_path = (
        bnet_exe.parent.parent.parent
        / "users"
        / "steamuser"
        / "AppData"
        / "Roaming"
        / "Battle.net"
        / "Battle.net.config"
    )
    log("Applying Wine/Battle.net stability tweaks ...")
    try:
        fixups.apply_battlenet_config_tweaks(config_path)
    except OSError as exc:
        log(f"Could not write Battle.net.config tweaks: {exc}")

    log("Setup complete.")
    return True
