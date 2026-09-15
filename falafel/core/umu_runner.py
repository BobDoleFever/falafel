"""Build and execute umu-run invocations.

Invocation-building is kept pure (no subprocess/env side effects) so it can be
unit tested without a real umu-run binary or Wine prefix. `run()` is the only
function that actually shells out.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .fixups import WINE_DLL_OVERRIDES

UMU_BIN = "umu-run"
INHIBIT_REASON = "falafel: Battle.net session active"


@dataclass(frozen=True)
class UmuInvocation:
    argv: list[str]
    env: dict[str, str]


def build_invocation(
    exe: str | Path,
    args: list[str] | None = None,
    *,
    prefix: Path,
    proton_path: str = "GE-Proton",
    gameid: str = "umu-default",
    store: str | None = None,
    base_env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    umu_bin: str | Path | None = None,
) -> UmuInvocation:
    """Build the argv/env for running `exe` under umu-run in `prefix`.

    `base_env` defaults to a copy of the current process environment (pass an
    empty dict in tests to assert on exactly what this function adds).
    Entries in `extra_env` win over everything else, so callers can override
    dll overrides etc. per-call if needed. `umu_bin` overrides the default
    "umu-run" on PATH with a resolved path (e.g. our bootstrapped copy from
    `umu_bootstrap.ensure_umu_run()`).
    """
    env = dict(os.environ if base_env is None else base_env)
    env["WINEPREFIX"] = str(prefix)
    env["GAMEID"] = gameid
    env["PROTONPATH"] = proton_path
    env["WINEDLLOVERRIDES"] = WINE_DLL_OVERRIDES
    if store:
        env["STORE"] = store
    if extra_env:
        env.update(extra_env)

    argv = [str(umu_bin) if umu_bin else UMU_BIN, str(exe), *(args or [])]
    return UmuInvocation(argv=argv, env=env)


def wrap_with_inhibit(argv: list[str], reason: str = INHIBIT_REASON) -> list[str]:
    """Prefix argv with systemd-inhibit so idle/sleep don't kick in while it runs.

    Steam normally handles screensaver/DPMS inhibition for games; a
    standalone umu-run launch like this one doesn't get that for free, so a
    Wine game session left alone (e.g. reading quest text, AFK in town) gets
    the screen dimmed and blanked like any idle desktop. systemd-inhibit's
    lock lasts exactly as long as its child process tree, which for
    "waitforexitandrun" is the whole Wine prefix session (Battle.net plus
    whatever game it launches) — so wrapping the outer umu-run invocation
    covers the entire play session, not just Battle.net's own window.

    Falls back to the unwrapped argv if systemd-inhibit isn't on PATH
    (non-systemd distros) — inhibition becomes best-effort, not a hard
    requirement.
    """
    inhibit_bin = shutil.which("systemd-inhibit")
    if inhibit_bin is None:
        return argv
    return [inhibit_bin, "--what=idle:sleep", f"--why={reason}", "--", *argv]


def run(
    invocation: UmuInvocation, *, background: bool = False, inhibit_idle: bool = False
) -> subprocess.CompletedProcess | subprocess.Popen:
    """Execute an UmuInvocation.

    background=True returns an unwaited Popen (for launching the client from
    a GUI without blocking); background=False runs to completion (for the
    Battle.net installer, which must finish before we proceed). inhibit_idle
    wraps the invocation with systemd-inhibit to keep the screen from
    dimming/blanking/sleeping for as long as it runs — pass it for launching
    the client (a play session can sit idle for a while), not for the
    installer (brief, interactive).
    """
    argv = wrap_with_inhibit(invocation.argv) if inhibit_idle else invocation.argv
    if background:
        return subprocess.Popen(argv, env=invocation.env)
    return subprocess.run(argv, env=invocation.env, check=False)
