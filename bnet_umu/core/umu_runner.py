"""Build and execute umu-run invocations.

Invocation-building is kept pure (no subprocess/env side effects) so it can be
unit tested without a real umu-run binary or Wine prefix. `run()` is the only
function that actually shells out.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .fixups import WINE_DLL_OVERRIDES

UMU_BIN = "umu-run"


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


def run(
    invocation: UmuInvocation, *, background: bool = False
) -> subprocess.CompletedProcess | subprocess.Popen:
    """Execute an UmuInvocation.

    background=True returns an unwaited Popen (for launching the client from
    a GUI without blocking); background=False runs to completion (for the
    Battle.net installer, which must finish before we proceed).
    """
    if background:
        return subprocess.Popen(invocation.argv, env=invocation.env)
    return subprocess.run(invocation.argv, env=invocation.env, check=False)
