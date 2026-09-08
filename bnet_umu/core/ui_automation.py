"""Best-effort automation of the Battle.net installer's UI via xdotool.

Battle.net-Setup.exe has no documented silent/unattended install flag (only
cosmetic `--lang=`/`--installpath=` args), so this drives its wizard the same
way a human would: press the default button through the install screens,
then close the login window it opens when done. This automates the existing
manual workaround ("don't log in during install, close that window instead")
— it never touches authentication itself.

Needs `xdotool` (X11/XWayland — the common case even under Wayland
compositors, since Wine runs through XWayland today). The window titles
below are best-effort and unverified on a real Wine prefix; if they don't
match, every step logs what it did (or couldn't do) and returns False rather
than hanging or guessing, so the caller can fall back to polling the
filesystem for whether the install actually finished regardless.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Callable

# Best-effort; verify against a real install and adjust if these don't match.
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


def wait_for_window_gone(
    title_substring: str,
    timeout: float = 120.0,
    poll_interval: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    deadline = clock() + timeout
    while True:
        if find_window(title_substring) is None:
            return True
        if clock() >= deadline:
            return False
        sleep_fn(poll_interval)


def press_key(window_id: str, key: str = "Return") -> None:
    subprocess.run(["xdotool", "key", "--window", window_id, key], check=False)


def close_window(window_id: str) -> None:
    subprocess.run(["xdotool", "windowclose", window_id], check=False)


def automate_installer_ui(
    log: Callable[[str], None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Drive the installer wizard and close the login window it ends on.

    Returns True if every step was confirmed; False on the first step it
    couldn't verify. This is purely a convenience — the caller should fall
    back to polling the filesystem for whether Battle.net actually installed
    either way, since a False here doesn't necessarily mean install failed,
    just that we couldn't drive/confirm the UI.
    """
    if not xdotool_available():
        log(
            "xdotool not found — install it (e.g. `pacman -S xdotool`) for "
            "hands-free setup, or complete the installer wizard yourself "
            "(close the login window instead of logging in)."
        )
        return False

    log("Waiting for the Battle.net installer window ...")
    installer_window = wait_for_window(INSTALLER_WINDOW_TITLE, timeout=60, sleep_fn=sleep_fn)
    if installer_window is None:
        log(
            "Couldn't find the installer window automatically — complete "
            "it yourself (close the login window instead of logging in)."
        )
        return False

    log("Installer window found — advancing through the wizard ...")
    for _ in range(3):
        press_key(installer_window, "Return")
        sleep_fn(2)

    log("Waiting for the install to finish ...")
    if not wait_for_window_gone(INSTALLER_WINDOW_TITLE, timeout=300, sleep_fn=sleep_fn):
        log("Installer window is still open after 5 minutes — check on it manually.")
        return False

    log("Waiting for the Battle.net login window to close automatically ...")
    login_window = wait_for_window(LOGIN_WINDOW_TITLE, timeout=60, sleep_fn=sleep_fn)
    if login_window is None:
        log(
            "Couldn't find the login window automatically — close it "
            "yourself instead of logging in; log in after setup finishes."
        )
        return False

    close_window(login_window)
    log("Closed the login window. Log in after setup finishes.")
    return True
