from pathlib import Path

from bnet_umu.core import umu_runner
from bnet_umu.core.fixups import WINE_DLL_OVERRIDES


def test_build_invocation_sets_expected_env():
    prefix = Path("/home/user/.local/share/bnet-umu/prefix")
    inv = umu_runner.build_invocation(
        "/path/to/Battle.net.exe",
        ["--extra-arg"],
        prefix=prefix,
        proton_path="GE-Proton9-5",
        gameid="umu-diablo2resurrected",
        store="battlenet",
        base_env={},
    )

    assert inv.argv == [
        umu_runner.UMU_BIN,
        "/path/to/Battle.net.exe",
        "--extra-arg",
    ]
    assert inv.env["WINEPREFIX"] == str(prefix)
    assert inv.env["GAMEID"] == "umu-diablo2resurrected"
    assert inv.env["PROTONPATH"] == "GE-Proton9-5"
    assert inv.env["STORE"] == "battlenet"
    assert inv.env["WINEDLLOVERRIDES"] == WINE_DLL_OVERRIDES


def test_build_invocation_omits_store_when_not_given():
    inv = umu_runner.build_invocation(
        "exe", prefix=Path("/tmp/prefix"), base_env={}
    )
    assert "STORE" not in inv.env


def test_extra_env_overrides_defaults():
    inv = umu_runner.build_invocation(
        "exe",
        prefix=Path("/tmp/prefix"),
        base_env={},
        extra_env={"WINEDLLOVERRIDES": "custom=n"},
    )
    assert inv.env["WINEDLLOVERRIDES"] == "custom=n"


def test_base_env_is_preserved_alongside_additions():
    inv = umu_runner.build_invocation(
        "exe", prefix=Path("/tmp/prefix"), base_env={"PATH": "/usr/bin"}
    )
    assert inv.env["PATH"] == "/usr/bin"
    assert inv.env["WINEPREFIX"] == "/tmp/prefix"


def test_wrap_with_inhibit_prefixes_systemd_inhibit(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemd-inhibit")
    result = umu_runner.wrap_with_inhibit(["umu-run", "Battle.net.exe"], reason="testing")
    assert result == [
        "/usr/bin/systemd-inhibit",
        "--what=idle:sleep",
        "--why=testing",
        "--",
        "umu-run",
        "Battle.net.exe",
    ]


def test_wrap_with_inhibit_falls_back_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    argv = ["umu-run", "Battle.net.exe"]
    assert umu_runner.wrap_with_inhibit(argv) is argv


def test_run_background_wraps_argv_when_inhibit_idle(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemd-inhibit")
    captured = {}

    class FakePopen:
        def __init__(self, argv, env):
            captured["argv"] = argv
            captured["env"] = env

    monkeypatch.setattr("subprocess.Popen", FakePopen)

    inv = umu_runner.UmuInvocation(argv=["umu-run", "Battle.net.exe"], env={"X": "1"})
    umu_runner.run(inv, background=True, inhibit_idle=True)

    assert captured["argv"][0] == "/usr/bin/systemd-inhibit"
    assert captured["argv"][-2:] == ["umu-run", "Battle.net.exe"]
    assert captured["env"] == {"X": "1"}


def test_run_background_does_not_wrap_by_default(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemd-inhibit")
    captured = {}

    class FakePopen:
        def __init__(self, argv, env):
            captured["argv"] = argv

    monkeypatch.setattr("subprocess.Popen", FakePopen)

    inv = umu_runner.UmuInvocation(argv=["umu-run", "Battle.net.exe"], env={})
    umu_runner.run(inv, background=True)

    assert captured["argv"] == ["umu-run", "Battle.net.exe"]
