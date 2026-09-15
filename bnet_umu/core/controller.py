"""Detecting whether a Steam Input virtual gamepad is currently available.

Doesn't touch any physical controller directly — Steam keeps exclusive raw
access to it while running, which is why a separate standalone driver would
fight with Steam. Instead, this checks for the thing a game launched via
bnet-umu actually reads: Steam Input's synthesized "Microsoft X-Box 360 pad"
uinput device, which Steam exposes system-wide (not just to Steam-launched
processes) for any controller it manages — a real Steam Controller
automatically, or an Xbox/PlayStation/Switch Pro/generic controller if
"Enable Steam Input for ... controllers" is turned on in Steam's own
Controller settings (on by default in current Steam).

Confirmed live (2026-09-15) that this virtual device passes straight through
umu-launcher's pressure-vessel sandbox with no bnet-umu-side wiring needed —
this module is a diagnostic, not a driver.
"""

from __future__ import annotations

from pathlib import Path

VIRTUAL_GAMEPAD_NAME_PREFIX = "Microsoft X-Box 360 pad"
INPUT_DEVICES_PATH = Path("/proc/bus/input/devices")


def find_virtual_gamepad(devices_path: Path = INPUT_DEVICES_PATH) -> str | None:
    """Return the name of Steam Input's virtual gamepad if one is present.

    Its absence doesn't mean controller support is broken — it just means
    Steam isn't currently running, or isn't currently managing a controller
    (e.g. the Steam Controller is powered off).
    """
    try:
        text = devices_path.read_text()
    except OSError:
        return None

    for line in text.splitlines():
        if line.startswith("N: Name=") and VIRTUAL_GAMEPAD_NAME_PREFIX in line:
            return line.split("N: Name=", 1)[1].strip().strip('"')
    return None
