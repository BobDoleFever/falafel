import json

from falafel.core.fixups import (
    WINE_DLL_OVERRIDES,
    apply_battlenet_config_tweaks,
    set_additional_launch_arguments,
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


def test_set_additional_launch_arguments_creates_file(tmp_path):
    config_path = tmp_path / "Battle.net.config"

    result = set_additional_launch_arguments(config_path, "osi", "-enablerespec")

    assert config_path.exists()
    assert result["Games"]["osi"]["AdditionalLaunchArguments"] == "-enablerespec"
    on_disk = json.loads(config_path.read_text())
    assert on_disk == result


def test_set_additional_launch_arguments_preserves_other_config(tmp_path):
    config_path = tmp_path / "Battle.net.config"
    config_path.write_text(json.dumps({"Client": {"HardwareAcceleration": False}}))

    result = set_additional_launch_arguments(config_path, "osi", "-enablerespec")

    assert result["Client"]["HardwareAcceleration"] is False
    assert result["Games"]["osi"]["AdditionalLaunchArguments"] == "-enablerespec"


def test_set_additional_launch_arguments_preserves_other_games(tmp_path):
    config_path = tmp_path / "Battle.net.config"
    config_path.write_text(
        json.dumps({"Games": {"wow": {"AdditionalLaunchArguments": "-someflag"}}})
    )

    result = set_additional_launch_arguments(config_path, "osi", "-enablerespec")

    assert result["Games"]["wow"]["AdditionalLaunchArguments"] == "-someflag"
    assert result["Games"]["osi"]["AdditionalLaunchArguments"] == "-enablerespec"


def test_set_additional_launch_arguments_empty_string_clears_it(tmp_path):
    config_path = tmp_path / "Battle.net.config"
    config_path.write_text(
        json.dumps({"Games": {"osi": {"AdditionalLaunchArguments": "-enablerespec"}}})
    )

    result = set_additional_launch_arguments(config_path, "osi", "")

    assert "AdditionalLaunchArguments" not in result["Games"]["osi"]


def test_set_additional_launch_arguments_clear_on_missing_game_is_a_noop(tmp_path):
    config_path = tmp_path / "Battle.net.config"

    result = set_additional_launch_arguments(config_path, "osi", "")

    assert config_path.exists()
    assert "osi" not in result.get("Games", {})
