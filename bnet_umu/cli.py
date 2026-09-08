"""CLI entry point (`bnet-umu`), sharing the same core/ as the GUI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from . import config as config_module
from .core import prefix, umu_bootstrap, umu_runner
from .core.games import GAMES
from .core.repair import repair as run_repair
from .core.setup_flow import run_setup


def cmd_status(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    print(f"Prefix: {cfg.prefix_path}")
    print(f"Proton: {cfg.proton_path}")
    print(f"External folders root: {cfg.external_root}")

    umu_path = umu_bootstrap.find_umu_run()
    if umu_path is None:
        print("umu-run: not found (will be downloaded automatically on `setup`)")
    else:
        origin = "system" if shutil.which(umu_runner.UMU_BIN) == str(umu_path) else "bundled"
        print(f"umu-run: found ({origin}) at {umu_path}")

    bnet_exe = prefix.find_battlenet_exe(cfg.prefix_path)
    print(f"Battle.net installed: {'yes' if bnet_exe else 'no'}")

    for game in GAMES.values():
        installed = prefix.find_game_install(cfg.prefix_path, game) is not None
        print(f"{game.name} detected: {'yes' if installed else 'no'}")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    ok = run_setup(cfg.prefix_path, cfg.proton_path, log=print)
    if not ok:
        return 1

    print("Run `bnet-umu launch` to start Battle.net.")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    bnet_exe = prefix.find_battlenet_exe(cfg.prefix_path)
    if bnet_exe is None:
        print("Battle.net isn't installed yet — run `bnet-umu setup` first.", file=sys.stderr)
        return 1

    umu_bin = umu_bootstrap.ensure_umu_run(log=print)
    invocation = umu_runner.build_invocation(
        bnet_exe,
        prefix=cfg.prefix_path,
        proton_path=cfg.proton_path,
        gameid="umu-default",
        store="battlenet",
        umu_bin=umu_bin,
    )
    umu_runner.run(invocation, background=True)

    for game in GAMES.values():
        try:
            prefix.expose_game_folders(cfg.prefix_path, game, cfg.external_root)
        except FileExistsError:
            pass
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    removed = run_repair(cfg.prefix_path)
    print(f"Cleared {len(removed)} director{'y' if len(removed) == 1 else 'ies'}:")
    for path in removed:
        print(f"  {path}")
    return 0


def cmd_open_saves(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    game = GAMES.get(args.game)
    if game is None:
        print(f"Unknown game id: {args.game}", file=sys.stderr)
        return 1

    target = cfg.external_root / "saves" / game.external_dirname
    if not target.exists():
        print("No save folder found yet — install and run the game at least once first.")
        return 1

    subprocess.Popen(["xdg-open", str(target)])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bnet-umu")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show prefix and install status").set_defaults(
        func=cmd_status
    )
    subparsers.add_parser(
        "setup", help="Create the prefix and install Battle.net"
    ).set_defaults(func=cmd_setup)
    subparsers.add_parser("launch", help="Launch Battle.net").set_defaults(func=cmd_launch)
    subparsers.add_parser(
        "repair", help="Clear broken Battle.net Agent state"
    ).set_defaults(func=cmd_repair)

    open_saves = subparsers.add_parser(
        "open-saves", help="Open a game's exposed save folder"
    )
    open_saves.add_argument("game", nargs="?", default="d2r", choices=list(GAMES.keys()))
    open_saves.set_defaults(func=cmd_open_saves)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
