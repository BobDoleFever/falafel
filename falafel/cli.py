"""CLI entry point (`falafel`), sharing the same core/ as the GUI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_module
from .core import cloud_sync, controller, prefix, save_backup, steam_shortcut, umu_bootstrap, umu_runner
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
            "(falafel reads Steam Input's shared virtual gamepad, same as "
            "any other app; it never touches the controller directly)"
        )
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    ok = run_setup(cfg.prefix_path, cfg.proton_path, log=print)
    if not ok:
        return 1

    print("Run `falafel launch` to start Battle.net.")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    bnet_exe = prefix.find_battlenet_exe(cfg.prefix_path)
    if bnet_exe is None:
        print("Battle.net isn't installed yet — run `falafel setup` first.", file=sys.stderr)
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
    launcher = shutil.which("falafel") or sys.argv[0]
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
    print(f'{verb} "{args.name}" as a Steam shortcut (launches via `falafel launch`).')
    if result.backup_path:
        print(f"Backed up the previous shortcuts.vdf to {result.backup_path}")
    if args.icon:
        print("Set as the shortcut's icon and library artwork.")
    print(
        "Restart Steam to see it (Steam > Exit, then reopen) — "
        "it won't pick up the change while already running."
    )
    return 0


def cmd_backup_saves(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    game = GAMES.get(args.game)
    if game is None:
        print(f"Unknown game id: {args.game}", file=sys.stderr)
        return 1

    try:
        zip_path = save_backup.backup_saves(game, cfg.prefix_path)
    except save_backup.NoSaveDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Backed up {game.name} saves to {zip_path}")
    return 0


def cmd_restore_saves(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    game = GAMES.get(args.game)
    if game is None:
        print(f"Unknown game id: {args.game}", file=sys.stderr)
        return 1

    try:
        result = save_backup.restore_saves(
            game, cfg.prefix_path, from_dir=Path(args.from_path), force=args.force
        )
    except save_backup.NewerLocalSavesError as exc:
        print(f"Refusing to restore: {exc}", file=sys.stderr)
        print(
            "Your current saves look newer than this backup. Pass --force to "
            "restore anyway — your current saves are always backed up first "
            "regardless, so this is still reversible.",
            file=sys.stderr,
        )
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Restored {game.name} saves from {args.from_path} to {result.restored_to}")
    if result.pre_restore_backup:
        print(f"Backed up your previous saves to {result.pre_restore_backup} first.")
    return 0


def _cloud_backup_dir(game_id: str) -> Path:
    return save_backup.default_backup_root() / game_id


def cmd_cloud_setup(args: argparse.Namespace) -> int:
    if not cloud_sync.rclone_available():
        print(
            "rclone not found. Install it first:\n"
            "  Arch:          sudo pacman -S rclone\n"
            "  Fedora:        sudo dnf install rclone\n"
            "  Debian/Ubuntu: sudo apt install rclone",
            file=sys.stderr,
        )
        return 1

    print(
        "Launching `rclone config` — set up a remote for Google Drive, iCloud "
        "Drive, or anything else rclone supports. You'll log in through "
        "rclone's own flow; falafel never sees your credentials."
    )
    return cloud_sync.run_rclone_config()


def cmd_cloud_push(args: argparse.Namespace) -> int:
    game = GAMES.get(args.game)
    if game is None:
        print(f"Unknown game id: {args.game}", file=sys.stderr)
        return 1
    if not cloud_sync.rclone_available():
        print("rclone not found — run `falafel cloud-setup` first.", file=sys.stderr)
        return 1

    local_dir = _cloud_backup_dir(game.id)
    remote_path = args.path or f"falafel-saves/{game.id}"
    print(f"Pushing {local_dir} -> {args.remote}:{remote_path} ...")
    result = cloud_sync.push(local_dir, args.remote, remote_path)
    return result.returncode


def cmd_cloud_pull(args: argparse.Namespace) -> int:
    game = GAMES.get(args.game)
    if game is None:
        print(f"Unknown game id: {args.game}", file=sys.stderr)
        return 1
    if not cloud_sync.rclone_available():
        print("rclone not found — run `falafel cloud-setup` first.", file=sys.stderr)
        return 1

    local_dir = _cloud_backup_dir(game.id)
    remote_path = args.path or f"falafel-saves/{game.id}"
    print(f"Pulling {args.remote}:{remote_path} -> {local_dir} ...")
    result = cloud_sync.pull(args.remote, remote_path, local_dir)
    return result.returncode


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
    parser = argparse.ArgumentParser(prog="falafel")
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

    backup_saves = subparsers.add_parser(
        "backup-saves", help="Snapshot a game's saves to a timestamped zip archive"
    )
    backup_saves.add_argument("game", nargs="?", default="d2r", choices=list(GAMES.keys()))
    backup_saves.set_defaults(func=cmd_backup_saves)

    restore_saves = subparsers.add_parser(
        "restore-saves", help="Restore saves from a backup zip (or directory)"
    )
    restore_saves.add_argument("game", nargs="?", default="d2r", choices=list(GAMES.keys()))
    restore_saves.add_argument(
        "--from", dest="from_path", required=True, help="Path to a backup .zip or directory"
    )
    restore_saves.add_argument(
        "--force",
        action="store_true",
        help="Restore even if local saves look newer than the backup (still backs them up first)",
    )
    restore_saves.set_defaults(func=cmd_restore_saves)

    subparsers.add_parser(
        "cloud-setup", help="Set up a cloud remote (Google Drive, iCloud Drive, etc.) via rclone"
    ).set_defaults(func=cmd_cloud_setup)

    cloud_push = subparsers.add_parser(
        "cloud-push", help="Upload local save backups to a cloud remote"
    )
    cloud_push.add_argument("game", nargs="?", default="d2r", choices=list(GAMES.keys()))
    cloud_push.add_argument("--remote", required=True, help="rclone remote name (see `rclone listremotes`)")
    cloud_push.add_argument(
        "--path", default=None, help="Path within the remote (default: falafel-saves/<game>)"
    )
    cloud_push.set_defaults(func=cmd_cloud_push)

    cloud_pull = subparsers.add_parser(
        "cloud-pull", help="Download save backups from a cloud remote"
    )
    cloud_pull.add_argument("game", nargs="?", default="d2r", choices=list(GAMES.keys()))
    cloud_pull.add_argument("--remote", required=True, help="rclone remote name (see `rclone listremotes`)")
    cloud_pull.add_argument(
        "--path", default=None, help="Path within the remote (default: falafel-saves/<game>)"
    )
    cloud_pull.set_defaults(func=cmd_cloud_pull)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    prefix.migrate_legacy_data_dir(log=print)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
