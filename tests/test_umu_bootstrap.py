import os
import stat
import tarfile
from pathlib import Path

from bnet_umu.core import umu_bootstrap


def _make_fake_zipapp_tar(tar_path: Path, tmp_path: Path) -> None:
    """Build a tarball matching the real release layout: umu/umu-run plus a
    umu/umu_run.py symlink, so extraction logic is tested against the real
    shape without hitting the network."""
    src_dir = tmp_path / "umu_src"
    src_dir.mkdir()
    umu_run_src = src_dir / "umu-run"
    umu_run_src.write_bytes(b"#!/usr/bin/env python3\nPK-fake-zip-contents")
    umu_run_src.chmod(0o644)

    with tarfile.open(tar_path, "w") as tar:
        tar.add(umu_run_src, arcname="umu/umu-run")


def test_find_umu_run_prefers_system_path(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/umu-run")
    assert umu_bootstrap.find_umu_run() == Path("/usr/bin/umu-run")


def test_find_umu_run_falls_back_to_bundled(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(umu_bootstrap, "bootstrap_dir", lambda: tmp_path)
    bundled = tmp_path / umu_bootstrap.UMU_RUN_BIN
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_bytes(b"fake")

    assert umu_bootstrap.find_umu_run() == bundled


def test_find_umu_run_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(umu_bootstrap, "bootstrap_dir", lambda: tmp_path / "nowhere")
    assert umu_bootstrap.find_umu_run() is None


def test_extract_zipapp_tar_installs_executable(tmp_path):
    tar_path = tmp_path / "umu-zipapp.tar"
    _make_fake_zipapp_tar(tar_path, tmp_path)
    dest_dir = tmp_path / "installed"

    result = umu_bootstrap.extract_zipapp_tar(tar_path, dest_dir)

    assert result == dest_dir / "umu-run"
    assert result.exists()
    assert result.read_bytes().startswith(b"#!/usr/bin/env python3")
    mode = result.stat().st_mode
    assert mode & stat.S_IXUSR


def test_extract_zipapp_tar_raises_if_umu_run_missing(tmp_path):
    tar_path = tmp_path / "empty.tar"
    with tarfile.open(tar_path, "w"):
        pass

    try:
        umu_bootstrap.extract_zipapp_tar(tar_path, tmp_path / "dest")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError for a tarball with no umu-run")
