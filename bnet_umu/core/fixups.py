"""Battle.net-under-Wine compatibility tweaks.

Transcribed from Lutris's Battle.net installer script and community reports
(umu-protonfixes' own gamefixes-battlenet module is an empty stub upstream, so
none of this is available to import from there). The DLL override syntax is
verified against real Wine semantics; the exact Battle.net.config JSON key
paths are best-effort and should be confirmed against a real
Battle.net.config on first run on real hardware.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Wine's WINEDLLOVERRIDES syntax: "dll1,dll2=mode". An empty mode after "="
# disables the dll entirely (Wine will not load it). locationapi is disabled
# because it causes the Battle.net Agent to hang on "Initializing..."; nvapi
# and nvapi64 are disabled because they can crash the Agent under Wine on
# non-Nvidia-passthrough setups.
WINE_DLL_OVERRIDES = "locationapi=;nvapi=;nvapi64="

# Dotted-path keys applied on top of the user's existing Battle.net.config
# (typically at drive_c/users/<user>/AppData/Roaming/Battle.net/Battle.net.config).
# These disable hardware acceleration, sound, and streaming features that are
# known to destabilize the Agent/client under Wine. Verify key names against
# an actual Battle.net.config before shipping — Blizzard does not document
# this schema and it has changed across client versions.
BATTLENET_CONFIG_TWEAKS: dict[str, Any] = {
    "Client.HardwareAcceleration": False,
    "Client.Sound.Enabled": False,
    "Client.Streaming.Enabled": False,
}


def _set_dotted(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def apply_battlenet_config_tweaks(
    config_path: Path, tweaks: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Merge `tweaks` into the Battle.net.config JSON file at `config_path`.

    Creates the file (and parent dirs) with just the tweaks if it doesn't
    exist yet. Returns the resulting parsed config.
    """
    tweaks = BATTLENET_CONFIG_TWEAKS if tweaks is None else tweaks

    if config_path.exists():
        data = json.loads(config_path.read_text())
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    for dotted_key, value in tweaks.items():
        _set_dotted(data, dotted_key, value)

    config_path.write_text(json.dumps(data, indent=2))
    return data
