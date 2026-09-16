"""Moving the local backup archives (see save_backup.py) to/from a cloud
remote via rclone — Google Drive, iCloud Drive, Dropbox, or anything else
rclone supports.

Deliberately thin: rclone already solves authentication (OAuth/2FA,
handled entirely by its own interactive `rclone config`, never by this
code — falafel never sees or touches your cloud credentials) and reliable
file transfer. All this module adds is running `rclone copy` in the right
direction against save_backup's backup directory.

Always `copy`, never `sync`: sync mirrors a destination to match a source
exactly, deleting anything at the destination that isn't in the source —
wrong here, since backup archives are meant to accumulate as an immutable
history. copy only adds/updates, so a push or pull can't delete a backup
that only exists on one side.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

RCLONE_BIN = "rclone"


def rclone_available() -> bool:
    return shutil.which(RCLONE_BIN) is not None


def run_rclone_config() -> int:
    """Launch `rclone config` interactively so the user sets up a remote
    themselves (Google Drive, iCloud Drive, etc.) through rclone's own
    OAuth/2FA flow. Never automated — that's inherently the user's own
    credentials to enter, same as any login."""
    return subprocess.call([RCLONE_BIN, "config"])


def push(local_dir: Path, remote: str, remote_path: str) -> subprocess.CompletedProcess:
    """Upload local_dir's contents to remote:remote_path (copy, not sync —
    never deletes anything on the remote)."""
    return subprocess.run(
        [RCLONE_BIN, "copy", str(local_dir), f"{remote}:{remote_path}"],
        check=False,
    )


def pull(remote: str, remote_path: str, local_dir: Path) -> subprocess.CompletedProcess:
    """Download remote:remote_path's contents into local_dir (copy, not
    sync — never deletes anything locally)."""
    local_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [RCLONE_BIN, "copy", f"{remote}:{remote_path}", str(local_dir)],
        check=False,
    )
