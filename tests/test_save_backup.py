import time
import zipfile

import pytest

from falafel.core import save_backup
from falafel.core.games import GAMES

D2R = GAMES["d2r"]


def _make_prefix_with_saves(tmp_path, files: dict[str, str]):
    prefix = tmp_path / "prefix"
    save_dir = prefix / "drive_c" / "users" / "steamuser" / "Saved Games" / "Diablo II Resurrected"
    save_dir.mkdir(parents=True)
    for name, content in files.items():
        (save_dir / name).write_text(content)
    return prefix, save_dir


def _sequential_timestamps(monkeypatch, module=save_backup):
    """Give each call to _timestamp() a distinct value, since real
    time.strftime only has 1-second resolution and tests run much faster
    than that."""
    counter = iter(range(1, 10_000))
    monkeypatch.setattr(module, "_timestamp", lambda: f"ts{next(counter):04d}")


def test_backup_saves_creates_verified_zip(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(tmp_path, {"Hero.d2s": "save-data"})
    backup_root = tmp_path / "backups"

    zip_path = save_backup.backup_saves(D2R, prefix, backup_root=backup_root)

    assert zip_path.exists()
    assert zip_path.parent == backup_root / "d2r"
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None
        assert zf.read("Hero.d2s").decode() == "save-data"


def test_backup_saves_raises_when_no_save_dir(tmp_path):
    prefix = tmp_path / "prefix"
    (prefix / "drive_c").mkdir(parents=True)

    with pytest.raises(save_backup.NoSaveDataError):
        save_backup.backup_saves(D2R, prefix, backup_root=tmp_path / "backups")


def test_backup_saves_never_overwrites_previous_snapshot(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(tmp_path, {"Hero.d2s": "v1"})
    backup_root = tmp_path / "backups"

    first = save_backup.backup_saves(D2R, prefix, backup_root=backup_root)
    (save_dir / "Hero.d2s").write_text("v2")
    second = save_backup.backup_saves(D2R, prefix, backup_root=backup_root)

    assert first != second
    assert first.exists() and second.exists()
    with zipfile.ZipFile(first) as zf:
        assert zf.read("Hero.d2s").decode() == "v1"
    with zipfile.ZipFile(second) as zf:
        assert zf.read("Hero.d2s").decode() == "v2"


def test_restore_saves_onto_fresh_prefix_with_no_save_dir_yet(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    # A backup made elsewhere...
    src_prefix, _ = _make_prefix_with_saves(tmp_path / "src", {"Hero.d2s": "restored-data"})
    backup_root = tmp_path / "backups"
    zip_path = save_backup.backup_saves(D2R, src_prefix, backup_root=backup_root)

    # ...restored onto a prefix that's never even launched D2R once, so the
    # save dir doesn't exist at all yet.
    fresh_prefix = tmp_path / "fresh_prefix"
    (fresh_prefix / "drive_c").mkdir(parents=True)

    result = save_backup.restore_saves(D2R, fresh_prefix, from_dir=zip_path, backup_root=backup_root)

    assert result.pre_restore_backup is None  # nothing there before, nothing to back up
    assert (result.restored_to / "Hero.d2s").read_text() == "restored-data"
    assert result.restored_to == fresh_prefix / "drive_c" / "users" / "steamuser" / "Saved Games" / "Diablo II Resurrected"


def test_restore_saves_backs_up_existing_data_before_overwriting(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(tmp_path, {"Hero.d2s": "old-local-data"})
    backup_root = tmp_path / "backups"

    incoming_zip = tmp_path / "incoming.zip"
    with zipfile.ZipFile(incoming_zip, "w") as zf:
        zf.writestr("Hero.d2s", "incoming-data")

    result = save_backup.restore_saves(
        D2R, prefix, from_dir=incoming_zip, force=True, backup_root=backup_root
    )

    assert result.pre_restore_backup is not None
    with zipfile.ZipFile(result.pre_restore_backup) as zf:
        assert zf.read("Hero.d2s").decode() == "old-local-data"
    assert (save_dir / "Hero.d2s").read_text() == "incoming-data"


def test_restore_saves_refuses_to_overwrite_newer_local_file(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(tmp_path, {"Hero.d2s": "played-more-recently"})
    backup_root = tmp_path / "backups"

    old_zip = tmp_path / "old.zip"
    with zipfile.ZipFile(old_zip, "w") as zf:
        zf.writestr("Hero.d2s", "stale-snapshot")
    # Make the local file's mtime clearly newer than the zip entry's.
    future = time.time() + 3600
    import os
    os.utime(save_dir / "Hero.d2s", (future, future))

    with pytest.raises(save_backup.NewerLocalSavesError) as exc_info:
        save_backup.restore_saves(D2R, prefix, from_dir=old_zip, backup_root=backup_root)

    assert "Hero.d2s" in exc_info.value.newer_files
    # Nothing was touched.
    assert (save_dir / "Hero.d2s").read_text() == "played-more-recently"


def test_restore_saves_force_overrides_newer_local_check(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(tmp_path, {"Hero.d2s": "played-more-recently"})
    backup_root = tmp_path / "backups"

    old_zip = tmp_path / "old.zip"
    with zipfile.ZipFile(old_zip, "w") as zf:
        zf.writestr("Hero.d2s", "stale-snapshot")
    future = time.time() + 3600
    import os
    os.utime(save_dir / "Hero.d2s", (future, future))

    result = save_backup.restore_saves(
        D2R, prefix, from_dir=old_zip, force=True, backup_root=backup_root
    )

    assert (save_dir / "Hero.d2s").read_text() == "stale-snapshot"
    assert result.pre_restore_backup is not None  # even forced, still backed up first


def test_restore_saves_never_deletes_local_files_absent_from_backup(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix, save_dir = _make_prefix_with_saves(
        tmp_path, {"KeptCharacter.d2s": "keep-me", "OtherFile.d2s": "keep-me-too"}
    )
    backup_root = tmp_path / "backups"

    incoming_zip = tmp_path / "incoming.zip"
    with zipfile.ZipFile(incoming_zip, "w") as zf:
        zf.writestr("NewCharacter.d2s", "new-data")

    save_backup.restore_saves(D2R, prefix, from_dir=incoming_zip, force=True, backup_root=backup_root)

    assert (save_dir / "KeptCharacter.d2s").read_text() == "keep-me"
    assert (save_dir / "OtherFile.d2s").read_text() == "keep-me-too"
    assert (save_dir / "NewCharacter.d2s").read_text() == "new-data"


def test_restore_saves_accepts_plain_directory_too(tmp_path, monkeypatch):
    _sequential_timestamps(monkeypatch)
    prefix = tmp_path / "prefix"
    (prefix / "drive_c").mkdir(parents=True)

    backup_dir = tmp_path / "loose_backup"
    backup_dir.mkdir()
    (backup_dir / "Hero.d2s").write_text("from-a-directory-not-a-zip")

    result = save_backup.restore_saves(D2R, prefix, from_dir=backup_dir, backup_root=tmp_path / "backups")

    assert (result.restored_to / "Hero.d2s").read_text() == "from-a-directory-not-a-zip"


def test_restore_saves_raises_on_corrupt_zip(tmp_path):
    prefix = tmp_path / "prefix"
    (prefix / "drive_c").mkdir(parents=True)
    bad_zip = tmp_path / "corrupt.zip"
    bad_zip.write_bytes(b"not actually a zip file")

    with pytest.raises(ValueError, match="not a valid backup archive"):
        save_backup.restore_saves(D2R, prefix, from_dir=bad_zip, backup_root=tmp_path / "backups")


def test_restore_saves_raises_file_not_found_for_missing_backup(tmp_path):
    prefix = tmp_path / "prefix"
    (prefix / "drive_c").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        save_backup.restore_saves(
            D2R, prefix, from_dir=tmp_path / "nope.zip", backup_root=tmp_path / "backups"
        )
