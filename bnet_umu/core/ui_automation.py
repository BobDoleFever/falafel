"""Closing the Battle.net post-install login window via xdotool.

Battle.net-Setup.exe has no documented silent/unattended install flag, so a
human still has to click through its wizard screens. This module does NOT
attempt to automate that: live testing on real hardware showed the wizard's
screens vary between runs (one run needed zero clicks, another showed a
"Select a Language" screen), and the install-progress screen's only button
is Cancel, focused by default — a blind keystroke sent at the wrong moment
aborted an install mid-way through during testing. Driving the wizard
without knowing which screen is actually showing is not safe.

What IS safe and automated here: once the installer hands off to
Battle.net.exe, it opens a login window that should be closed rather than
logged into (a known Wine workaround for a broken first-run auth flow).
That window's title is reliable and closing it is a single, low-risk action,
so `close_login_window` polls for it and closes it automatically.

Needs `xdotool` (X11/XWayland — the common case even under Wayland
compositors, since Wine runs through XWayland today).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Callable

# Confirmed against a real Battle.net install on Arch Linux (GE-Proton via
# umu-launcher). INSTALLER_WINDOW_TITLE is intentionally unused for
# automation (see module docstring) — kept as verified documentation.
INSTALLER_WINDOW_TITLE = "Battle.net Setup"
LOGIN_WINDOW_TITLE = "Battle.net Login"


def xdotool_available() -> bool:
    return shutil.which("xdotool") is not None


def find_window(title_substring: str) -> str | None:
    result = subprocess.run(
        ["xdotool", "search", "--name", title_substring],
        capture_output=True,
        text=True,
        check=False,
    )
    window_ids = [line for line in result.stdout.splitlines() if line.strip()]
    return window_ids[0] if window_ids else None


def wait_for_window(
    title_substring: str,
    timeout: float = 60.0,
    poll_interval: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str | None:
    deadline = clock() + timeout
    while True:
        window_id = find_window(title_substring)
        if window_id:
            return window_id
        if clock() >= deadline:
            return None
        sleep_fn(poll_interval)


def close_window(window_id: str) -> None:
    subprocess.run(["xdotool", "windowclose", window_id], check=False)


def close_login_window(
    log: Callable[[str], None] = print,
    timeout: float = 60.0,
    poll_interval: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll for the Battle.net login window and close it if it appears.

    Returns False (without raising) if xdotool isn't installed or the window
    never appears within `timeout` — the caller should fall back to telling
    the user to close it themselves rather than logging in.
    """
    if not xdotool_available():
        log(
            "xdotool not found — install it (e.g. `pacman -S xdotool`) to "
            "have the login window closed automatically, or close it "
            "yourself instead of logging in."
        )
        return False

    log(
        "Waiting for the Battle.net login window (won't log in — just "
        "closing it, per the known Wine first-run auth workaround) ..."
    )
    login_window = wait_for_window(
        LOGIN_WINDOW_TITLE, timeout=timeout, poll_interval=poll_interval,
        sleep_fn=sleep_fn, clock=clock,
    )
    if login_window is None:
        log(
            "Couldn't find the login window automatically — if one is open, "
            "close it yourself instead of logging in."
        )
        return False

    close_window(login_window)
    log("Closed the login window. Log in after setup finishes.")
    return True
