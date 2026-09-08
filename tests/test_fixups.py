import json

from bnet_umu.core.fixups import (
    WINE_DLL_OVERRIDES,
    apply_battlenet_config_tweaks,
)


def test_wine_dll_overrides_disables_expected_dlls():
    for dll in ("locationapi", "nvapi", "nvapi64"):
        assert f"{dll}=" in WINE_DLL_OVERRIDES


def test_apply_config_tweaks_creates_file(tmp_path):
    config_path = tmp_path / "AppData" / "Roaming" / "Battle.net" / "Battle.net.config"
    result = apply_battlenet_config_tweaks(config_path)

    assert config_path.exists()
    assert result["Client"]["HardwareAcceleration"] is False
    assert result["Client"]["Sound"]["Enabled"] is False


def test_apply_config_tweaks_merges_into_existing_file(tmp_path):
    config_path = tmp_path / "Battle.net.config"
    config_path.write_text(json.dumps({"Client": {"SomeUnrelatedSetting": True}}))

    result = apply_battlenet_config_tweaks(config_path)

    assert result["Client"]["SomeUnrelatedSetting"] is True
    assert result["Client"]["HardwareAcceleration"] is False

    on_disk = json.loads(config_path.read_text())
    assert on_disk == result
