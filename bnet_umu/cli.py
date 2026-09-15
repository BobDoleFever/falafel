"""CLI entry point (`bnet-umu`), sharing the same core/ as the GUI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_module
from .core import controller, prefix, steam_shortcut, umu_bootstrap, umu_runner
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

    gamepad = controller.find_virtual_gamepad()
    if gamepad:
        print(f"Controller: {gamepad} detected (via Steam Input)")
    else:
        print(
            "Controller: none detected — for gamepad support, keep Steam "
            "running in the background with the controller connected "
            "(bnet-umu reads Steam Input's shared virtual gamepad, same as "
            "any other app; it never touches the controller directly)"
        )
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
    umu_runner.run(invocation, background=True, inhibit_idle=True)

    for game in GAMES.values():
        try:
            prefix.expose_game_folders(cfg.prefix_path, game, cfg.external_root)
        except FileExistsError:
            pass
    return 0


def cmd_add_to_steam(args: argparse.Namespace) -> int:
    launcher = shutil.which("bnet-umu") or sys.argv[0]
    launcher_path = Path(launcher).resolve()

    if args.icon and not Path(args.icon).is_file():
        print(f"Icon file not found: {args.icon}", file=sys.stderr)
        return 1

    try:
        result = steam_shortcut.add_shortcut(
            exe=str(launcher_path),
            app_name=args.name,
            start_dir=str(launcher_path.parent),
            launch_options="launch",
            icon=args.icon or "",
        )
    except FileNotFoundError as exc:
        print(f"Couldn't find your Steam userdata directory: {exc}", file=sys.stderr)
        return 1

    verb = "Updated" if result.was_update else "Added"
    print(f'{verb} "{args.name}" as a Steam shortcut (launches via `bnet-umu launch`).')
    if result.backup_path:
        print(f"Backed up the previous shortcuts.vdf to {result.backup_path}")
    if args.icon:
        print("Set as the shortcut's icon and library artwork.")
    print(
        "Restart Steam to see it (Steam > Exit, then reopen) — "
        "it won't pick up the change while already running."
    )
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

    add_to_steam = subparsers.add_parser(
        "add-to-steam", help="Add this as a Non-Steam Game shortcut in Steam"
    )
    add_to_steam.add_argument(
        "--name", default="Battle.net", help="Display name in Steam (default: Battle.net)"
    )
    add_to_steam.add_argument(
        "--icon", default=None, help="Path to an icon/logo image file to use"
    )
    add_to_steam.set_defaults(func=cmd_add_to_steam)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
