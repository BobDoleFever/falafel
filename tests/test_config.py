from pathlib import Path

from bnet_umu import config as config_module


def test_load_returns_defaults_when_missing(tmp_path):
    cfg = config_module.load(tmp_path / "does-not-exist.toml")
    assert cfg.proton_path == "GE-Proton"
    assert cfg.installed == {}


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "config.toml"
    cfg = config_module.AppConfig(
        prefix_path=Path("/home/user/.local/share/bnet-umu/prefix"),
        external_root=Path("/home/user/Games/battlenet"),
        proton_path="GE-Proton9-5",
        installed={"d2r": True},
    )

    config_module.save(cfg, path)
    assert path.exists()

    loaded = config_module.load(path)
    assert loaded.prefix_path == cfg.prefix_path
    assert loaded.external_root == cfg.external_root
    assert loaded.proton_path == cfg.proton_path
    assert loaded.installed == cfg.installed


def test_saved_file_is_valid_toml(tmp_path):
    import tomllib

    path = tmp_path / "config.toml"
    cfg = config_module.AppConfig(installed={"d2r": False})
    config_module.save(cfg, path)

    with open(path, "rb") as f:
        data = tomllib.load(f)

    assert data["proton_path"] == "GE-Proton"
    assert data["games"]["installed"]["d2r"] is False
