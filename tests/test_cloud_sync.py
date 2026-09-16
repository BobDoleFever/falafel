import subprocess
from pathlib import Path

from falafel.core import cloud_sync


def test_rclone_available_true(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/rclone")
    assert cloud_sync.rclone_available() is True


def test_rclone_available_false(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert cloud_sync.rclone_available() is False


def test_run_rclone_config_calls_rclone_config(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "call", lambda argv: calls.append(argv) or 0)

    result = cloud_sync.run_rclone_config()

    assert calls == [["rclone", "config"]]
    assert result == 0


def test_push_uses_copy_not_sync(monkeypatch, tmp_path):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    cloud_sync.push(tmp_path / "backups" / "d2r", "gdrive", "falafel-saves/d2r")

    assert captured["argv"] == [
        "rclone",
        "copy",
        str(tmp_path / "backups" / "d2r"),
        "gdrive:falafel-saves/d2r",
    ]


def test_pull_uses_copy_not_sync_and_creates_local_dir(monkeypatch, tmp_path):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    local_dir = tmp_path / "backups" / "d2r"

    cloud_sync.pull("gdrive", "falafel-saves/d2r", local_dir)

    assert captured["argv"] == ["rclone", "copy", "gdrive:falafel-saves/d2r", str(local_dir)]
    assert local_dir.is_dir()
