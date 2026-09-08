from bnet_umu.core.games import GAMES, get_game


def test_d2r_registered():
    game = GAMES["d2r"]
    assert game.id == "d2r"
    assert game.name == "Diablo II: Resurrected"
    assert game.install_glob.endswith("D2R.exe")
    assert "Saved Games" in game.save_glob


def test_get_game_unknown_raises():
    try:
        get_game("not-a-real-game")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown game id")
