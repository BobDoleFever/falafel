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
