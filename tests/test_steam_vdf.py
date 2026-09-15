import pytest

from falafel.core import steam_vdf


def test_round_trips_nested_structure():
    original = {
        "shortcuts": {
            "0": {
                "appid": 3735928559,
                "AppName": "Example Game",
                "Exe": '"/home/user/game.exe"',
                "tags": {},
            },
        },
    }

    data = steam_vdf.dumps(original)
    assert steam_vdf.loads(data) == original


def test_dumps_preserves_field_order():
    d = {"b": "second", "a": "first"}
    data = steam_vdf.dumps(d)
    # 'b' should appear before 'a' in the byte stream since dict preserves
    # insertion order and dumps doesn't reorder.
    assert data.index(b"b\x00") < data.index(b"a\x00")


def test_loads_rejects_trailing_data():
    valid = steam_vdf.dumps({"x": "y"})
    with pytest.raises(ValueError, match="trailing data"):
        steam_vdf.loads(valid + b"\x00garbage")


def test_loads_rejects_unknown_type_byte():
    # type byte 0x05 doesn't exist in this grammar
    bad = bytes([0x05]) + b"key\x00" + bytes([steam_vdf.END_MARKER])
    with pytest.raises(ValueError, match="unsupported VDF type byte"):
        steam_vdf.loads(bad)


def test_empty_root_round_trips():
    assert steam_vdf.loads(steam_vdf.dumps({})) == {}


def test_loads_parses_hand_built_bytes_matching_real_shortcuts_vdf_shape():
    # Hand-built (not round-tripped through dumps()) to independently verify
    # the parser against the actual on-disk shape of a real shortcuts.vdf:
    # root -> "shortcuts" map -> "0" map -> appid (uint32), AppName/Exe
    # (strings), tags (empty nested map) -> nested/outer END_MARKERs.
    data = (
        b"\x00shortcuts\x00"
        b"\x000\x00"
        b"\x02appid\x00\x78\x56\x34\x12"
        b"\x01AppName\x00Example Game\x00"
        b"\x01Exe\x00\x22/home/user/game.exe\x22\x00"
        b"\x00tags\x00\x08"
        b"\x08"
        b"\x08"
        b"\x08"
    )

    result = steam_vdf.loads(data)

    assert result["shortcuts"]["0"]["appid"] == 0x12345678
    assert result["shortcuts"]["0"]["AppName"] == "Example Game"
    assert result["shortcuts"]["0"]["Exe"] == '"/home/user/game.exe"'
    assert result["shortcuts"]["0"]["tags"] == {}
