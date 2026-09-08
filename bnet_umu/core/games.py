"""Registry of Blizzard games supported by bnet-umu.

Each entry describes how to find a game's install and save data inside the
Battle.net Wine prefix, keyed by glob patterns rather than fixed paths since
the exact folder layout (and the Wine "user" name inside the prefix) can vary
by Proton build. Verify these globs against a real install before relying on
them; they're transcribed from community reports, not confirmed on-machine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameDef:
    id: str
    name: str
    # umu GAMEID / STORE used for protonfixes lookups (see umu-protonfixes'
    # gamefixes-battlenet, which is currently an empty stub upstream).
    umu_gameid: str
    store: str
    # Glob pattern, relative to the prefix's drive_c/, that matches the game's
    # main executable once installed.
    install_glob: str
    # Glob pattern, relative to drive_c/, that matches the save-data directory.
    save_glob: str
    # Directory name used when exposing folders under ~/Games/battlenet/.
    external_dirname: str


GAMES: dict[str, GameDef] = {
    "d2r": GameDef(
        id="d2r",
        name="Diablo II: Resurrected",
        umu_gameid="umu-diablo2resurrected",
        store="battlenet",
        install_glob="Program Files (x86)/Diablo II Resurrected/D2R.exe",
        save_glob="users/*/Saved Games/Diablo II Resurrected",
        external_dirname="d2r",
    ),
}


def get_game(game_id: str) -> GameDef:
    try:
        return GAMES[game_id]
    except KeyError as exc:
        raise ValueError(f"Unknown game id: {game_id!r}") from exc
