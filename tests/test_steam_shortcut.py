from bnet_umu.core import steam_shortcut, steam_vdf


def _make_userdata(tmp_path):
    config_dir = tmp_path / "Steam" / "userdata" / "12345" / "config"
    config_dir.mkdir(parents=True)
    return tmp_path / "Steam", config_dir


def test_find_userdata_config_dir_picks_the_only_one(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)
    assert steam_shortcut.find_userdata_config_dir(steam_root) == config_dir


def test_find_userdata_config_dir_raises_when_missing(tmp_path):
    try:
        steam_shortcut.find_userdata_config_dir(tmp_path / "nowhere")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_add_shortcut_creates_file_with_one_entry(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)

    result = steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net",
        start_dir="/home/user/.local/bin",
        launch_options="launch",
        steam_root=steam_root,
    )

    assert result.was_update is False
    assert result.backup_path is None
    root = steam_vdf.loads(result.shortcuts_path.read_bytes())
    entry = root["shortcuts"]["0"]
    assert entry["AppName"] == "Battle.net"
    assert entry["Exe"] == '"/home/user/.local/bin/bnet-umu"'
    assert entry["LaunchOptions"] == "launch"
    assert entry["appid"] == result.appid


def test_add_shortcut_preserves_existing_unrelated_entries(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)
    existing = {
        "shortcuts": {
            "0": {
                "appid": 111,
                "AppName": "Some Other Game",
                "Exe": '"/home/user/other/game.exe"',
                "StartDir": "/home/user/other",
                "icon": "",
                "tags": {},
                "sortas": "Other Game",
            },
        },
    }
    (config_dir / "shortcuts.vdf").write_bytes(steam_vdf.dumps(existing))

    steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net",
        start_dir="/home/user/.local/bin",
        steam_root=steam_root,
    )

    root = steam_vdf.loads((config_dir / "shortcuts.vdf").read_bytes())
    assert len(root["shortcuts"]) == 2
    assert root["shortcuts"]["0"]["AppName"] == "Some Other Game"
    assert root["shortcuts"]["0"]["sortas"] == "Other Game"
    assert root["shortcuts"]["1"]["AppName"] == "Battle.net"


def test_add_shortcut_is_idempotent_by_exe_path(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)

    steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net",
        start_dir="/home/user/.local/bin",
        steam_root=steam_root,
    )
    result = steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net (renamed)",
        start_dir="/home/user/.local/bin",
        steam_root=steam_root,
    )

    assert result.was_update is True
    root = steam_vdf.loads(result.shortcuts_path.read_bytes())
    assert len(root["shortcuts"]) == 1
    assert root["shortcuts"]["0"]["AppName"] == "Battle.net (renamed)"


def test_add_shortcut_backs_up_existing_file_before_writing(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)
    (config_dir / "shortcuts.vdf").write_bytes(steam_vdf.dumps({"shortcuts": {}}))

    result = steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net",
        start_dir="/home/user/.local/bin",
        steam_root=steam_root,
    )

    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert steam_vdf.loads(result.backup_path.read_bytes()) == {"shortcuts": {}}


def test_add_shortcut_writes_icon_field_and_grid_art(tmp_path):
    steam_root, config_dir = _make_userdata(tmp_path)
    icon_path = tmp_path / "logo.png"
    icon_path.write_bytes(b"fake-png-bytes")

    result = steam_shortcut.add_shortcut(
        exe="/home/user/.local/bin/bnet-umu",
        app_name="Battle.net",
        start_dir="/home/user/.local/bin",
        icon=str(icon_path),
        steam_root=steam_root,
    )

    root = steam_vdf.loads(result.shortcuts_path.read_bytes())
    assert root["shortcuts"]["0"]["icon"] == str(icon_path)

    grid_dir = config_dir / "grid"
    written = {p.name for p in grid_dir.iterdir()}
    assert f"{result.appid}.png" in written
    assert f"{result.appid}_icon.png" in written
