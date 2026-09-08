from pathlib import Path

import pytest

from bnet_umu.core import prefix
from bnet_umu.core.games import GAMES


def test_xdg_data_home_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert prefix.xdg_data_home() == tmp_path


def test_xdg_data_home_falls_back_to_local_share(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert prefix.xdg_data_home() == Path.home() / ".local" / "share"


def _make_fake_prefix(tmp_path: Path) -> Path:
    pfx = tmp_path / "prefix"
    d2r_dir = pfx / "drive_c" / "Program Files (x86)" / "Diablo II Resurrected"
    d2r_dir.mkdir(parents=True)
    (d2r_dir / "D2R.exe").write_text("")

    save_dir = pfx / "drive_c" / "users" / "steamuser" / "Saved Games" / "Diablo II Resurrected"
    save_dir.mkdir(parents=True)
    (save_dir / "profile.d2s").write_text("")

    bnet_dir = pfx / "drive_c" / "Program Files (x86)" / "Battle.net"
    bnet_dir.mkdir(parents=True)
    (bnet_dir / "Battle.net.exe").write_text("")

    return pfx


def test_find_game_install_and_battlenet_exe(tmp_path):
    pfx = _make_fake_prefix(tmp_path)
    d2r = GAMES["d2r"]

    install = prefix.find_game_install(pfx, d2r)
    assert install is not None
    assert install.name == "D2R.exe"

    bnet_exe = prefix.find_battlenet_exe(pfx)
    assert bnet_exe is not None
    assert bnet_exe.name == "Battle.net.exe"


def test_find_game_install_returns_none_when_absent(tmp_path):
    pfx = tmp_path / "empty_prefix"
    (pfx / "drive_c").mkdir(parents=True)
    d2r = GAMES["d2r"]
    assert prefix.find_game_install(pfx, d2r) is None


def test_expose_folder_creates_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("hi")

    target = tmp_path / "external" / "saves" / "d2r"
    result = prefix.expose_folder(source, target)

    assert result.is_symlink()
    assert (target / "file.txt").read_text() == "hi"


def test_expose_folder_idempotent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "external" / "saves" / "d2r"

    prefix.expose_folder(source, target)
    # second call with the same source should not raise
    prefix.expose_folder(source, target)


def test_expose_folder_raises_on_conflicting_target(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    other_source = tmp_path / "other_source"
    other_source.mkdir()
    target = tmp_path / "external" / "saves" / "d2r"

    prefix.expose_folder(source, target)
    with pytest.raises(FileExistsError):
        prefix.expose_folder(other_source, target)


def test_expose_game_folders_end_to_end(tmp_path):
    pfx = _make_fake_prefix(tmp_path)
    external_root = tmp_path / "external"
    d2r = GAMES["d2r"]

    result = prefix.expose_game_folders(pfx, d2r, external_root)

    assert result["install"] is not None
    assert result["save"] is not None
    assert (external_root / "saves" / "d2r" / "profile.d2s").exists()
    assert (external_root / "installs" / "d2r" / "D2R.exe").exists()


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_wait_for_battlenet_exe_returns_immediately_if_present(tmp_path):
    pfx = _make_fake_prefix(tmp_path)
    clock = _FakeClock()

    result = prefix.wait_for_battlenet_exe(
        pfx, timeout=10, poll_interval=1, sleep_fn=clock.sleep, clock=clock.clock
    )

    assert result is not None
    assert result.name == "Battle.net.exe"
    assert clock.now == 0.0


def test_wait_for_battlenet_exe_polls_until_it_appears(tmp_path, monkeypatch):
    pfx = tmp_path / "prefix"
    (pfx / "drive_c").mkdir(parents=True)
    clock = _FakeClock()

    results = iter([None, None, pfx / "drive_c" / "fake" / "Battle.net.exe"])
    monkeypatch.setattr(prefix, "find_battlenet_exe", lambda p: next(results))

    result = prefix.wait_for_battlenet_exe(
        pfx, timeout=10, poll_interval=1, sleep_fn=clock.sleep, clock=clock.clock
    )

    assert result is not None
    assert result.name == "Battle.net.exe"
    assert clock.now == 2.0


def test_wait_for_battlenet_exe_times_out_when_never_created(tmp_path):
    pfx = tmp_path / "empty_prefix"
    (pfx / "drive_c").mkdir(parents=True)
    clock = _FakeClock()

    result = prefix.wait_for_battlenet_exe(
        pfx, timeout=5, poll_interval=1, sleep_fn=clock.sleep, clock=clock.clock
    )

    assert result is None
    assert clock.now >= 5
