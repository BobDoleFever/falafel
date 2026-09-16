"""Local save snapshots: the transport-agnostic core of cross-machine sync.

Deliberately not a sync engine. `backup_saves` takes a timestamped snapshot
of a game's save folder as a single zip archive; `restore_saves` applies one
back. Moving archives between machines (or through a cloud remote) is
someone else's solved problem — see cloud_sync.py, which is just a thin
`rclone copy` wrapper around this module's backup directory.

Why zip archives rather than loose directory copies: a zip is one file, so
there's no "half-copied snapshot" state to worry about — it's written to a
temp path, fully verified (every source file present with a matching CRC),
and only then atomically renamed into place, so a crash or interruption
mid-backup can never leave a corrupt file at the name callers rely on.
Restoring re-verifies the archive's CRCs again before touching anything.

Safety model on top of that: snapshots are immutable and additive
(backup_saves never overwrites an old snapshot; restore_saves never deletes
local files, and refuses to overwrite anything locally newer than what's in
the snapshot being restored unless told to force it, always taking a fresh
zip backup of whatever's currently live first) — so a botched or duplicate
sync can leave stray extra files or extra backup archives lying around, but
it can't silently destroy save progress.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .games import GameDef
from .prefix import find_save_dir, resolve_save_dir


def default_backup_root() -> Path:
    return Path.home() / "falafel-save-backups"


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


class NoSaveDataError(Exception):
    """Raised by backup_saves when the game has no save dir yet to back up."""


class NewerLocalSavesError(Exception):
    """Raised by restore_saves when local saves look newer than the backup.

    `newer_files` lists the filenames that would be overwritten with older
    data — pass force=True to proceed anyway once you've reviewed them.
    """

    def __init__(self, newer_files: list[str]):
        self.newer_files = newer_files
        super().__init__(
            f"{len(newer_files)} local save file(s) are newer than the backup "
            f"being restored: {', '.join(newer_files)}"
        )


def _zip_dir(src: Path, zip_path: Path) -> Path:
    """Zip src's contents into zip_path (files at the archive root).

    Written to a temp path first and only renamed into place at zip_path
    after every source file is confirmed present in the archive with a
    passing CRC check — so callers never see a partially-written backup at
    the name they asked for.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = zip_path.with_name(zip_path.name + ".tmp")
    src_files = [p for p in src.rglob("*") if p.is_file()]

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src_files:
            zf.write(f, f.relative_to(src).as_posix())

    with zipfile.ZipFile(tmp_path) as zf:
        bad_entry = zf.testzip()
        if bad_entry is not None:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"backup verification failed: corrupt entry {bad_entry!r}")
        archived = set(zf.namelist())
        expected = {f.relative_to(src).as_posix() for f in src_files}
        missing = expected - archived
        if missing:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"backup verification failed: {len(missing)} file(s) missing from "
                f"archive: {sorted(missing)[:5]}"
            )

    tmp_path.replace(zip_path)
    return zip_path


def backup_saves(
    game: GameDef, prefix: Path, *, backup_root: Path | None = None
) -> Path:
    """Snapshot the game's current save dir to a new timestamped zip archive.

    Never overwrites a previous snapshot (each call gets its own timestamp).
    Raises NoSaveDataError if the game has no save dir yet (nothing played).
    """
    save_dir = find_save_dir(prefix, game)
    if save_dir is None:
        raise NoSaveDataError(
            f"No save data found for {game.name} — play it at least once first."
        )

    backup_root = backup_root or default_backup_root()
    zip_path = backup_root / game.id / f"{_timestamp()}.zip"
    return _zip_dir(save_dir, zip_path)


def _extract_to_temp(archive: Path) -> tuple[Path, tempfile.TemporaryDirectory]:
    """Extract a backup zip to a fresh temp dir, re-verifying its CRCs first.

    Caller must call .cleanup() on the returned TemporaryDirectory.
    """
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"not a valid backup archive (not a zip file): {archive}")

    tmp = tempfile.TemporaryDirectory(prefix="falafel-restore-")
    try:
        with zipfile.ZipFile(archive) as zf:
            bad_entry = zf.testzip()
            if bad_entry is not None:
                raise RuntimeError(f"backup archive is corrupt: bad entry {bad_entry!r} in {archive}")
            zf.extractall(tmp.name)
    except Exception:
        tmp.cleanup()
        raise
    return Path(tmp.name), tmp


def _copy_verified(src: Path, dest: Path) -> Path:
    """Copy src's contents into dest (never deleting anything already in
    dest) and verify every file from src actually landed.

    Deliberately a subset check, not exact equality: dest may already have
    files src doesn't (e.g. restoring onto a save folder with a character
    the snapshot doesn't know about) — those are meant to survive untouched,
    not count as a verification failure.
    """
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    src_files = [p.relative_to(src) for p in src.rglob("*") if p.is_file()]
    missing = [f for f in src_files if not (dest / f).is_file()]
    if missing:
        raise RuntimeError(
            f"copy verification failed: {len(missing)} of {len(src_files)} file(s) "
            f"missing from {dest} after copy: {', '.join(str(m) for m in missing[:5])}"
        )
    return dest


def _newer_local_files(target: Path, backup: Path) -> list[str]:
    newer = []
    for f in sorted(target.iterdir()):
        if not f.is_file():
            continue
        counterpart = backup / f.name
        if not counterpart.exists() or f.stat().st_mtime > counterpart.stat().st_mtime:
            newer.append(f.name)
    return newer


@dataclass(frozen=True)
class RestoreResult:
    restored_to: Path
    pre_restore_backup: Path | None


def restore_saves(
    game: GameDef,
    prefix: Path,
    *,
    from_dir: Path,
    force: bool = False,
    backup_root: Path | None = None,
) -> RestoreResult:
    """Restore a backup zip (or, for convenience, a plain directory) into the
    game's save dir.

    Always backs up whatever's currently there first, as a fresh zip archive
    (restoring is never a one-way door). Refuses to proceed if any local
    file is newer than its counterpart in the snapshot being restored —
    pass force=True once you've confirmed that's what you want.
    """
    if not from_dir.exists():
        raise FileNotFoundError(f"backup not found: {from_dir}")

    if from_dir.is_dir():
        source_dir, temp = from_dir, None
    else:
        source_dir, temp = _extract_to_temp(from_dir)

    try:
        target = resolve_save_dir(prefix, game)
        backup_root = backup_root or default_backup_root()

        pre_restore_backup = None
        if target.is_dir() and any(target.iterdir()):
            if not force:
                newer = _newer_local_files(target, source_dir)
                if newer:
                    raise NewerLocalSavesError(newer)
            pre_restore_backup = _zip_dir(
                target, backup_root / game.id / f"{_timestamp()}-pre-restore.zip"
            )

        _copy_verified(source_dir, target)
        return RestoreResult(restored_to=target, pre_restore_backup=pre_restore_backup)
    finally:
        if temp is not None:
            temp.cleanup()
