"""Recovery from the common "Battle.net Agent broke after an update" failure.

The documented manual fix is to delete the Agent's ProgramData directories
and let Battle.net recreate them on next launch.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .prefix import drive_c

RELATIVE_PATHS_TO_CLEAR = (
    "ProgramData/Battle.net/Agent",
    "ProgramData/Blizzard Entertainment",
)


def repair(prefix: Path) -> list[Path]:
    """Delete known-bad Agent state. Returns the paths actually removed."""
    removed: list[Path] = []
    for relative in RELATIVE_PATHS_TO_CLEAR:
        target = drive_c(prefix) / relative
        if target.exists():
            shutil.rmtree(target)
            removed.append(target)
    return removed
