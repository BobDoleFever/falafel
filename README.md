# bnet-umu

A standalone, Steam-independent Battle.net launcher for Linux, built on
[umu-launcher](https://github.com/Open-Wine-Components/umu-launcher). Manages
a dedicated Wine prefix for Battle.net, applies known Wine compatibility
tweaks, exposes save/install folders at normal host paths, and gives one-click
setup / launch / repair. Initial target game: **Diablo II: Resurrected**.

Not supported: games with kernel-level anticheat under their Battle.net
listing (e.g. Overwatch, Call of Duty) — that's a Proton/anticheat-vendor
limitation, not something this tool can work around.

## Why not Diablo IV (yet)?

D3/D2R/WoW/StarCraft have a long, stable history under Wine. Diablo IV
briefly shipped a client patch (June 2026) with a deliberate Wine-detection
breakpoint that intentionally crashed the game — patched within days by
Valve, but a sign that D4 can silently break independent of anything this
tool does. D2R was chosen as the initial target specifically to avoid that
risk profile.

## Prerequisites (on your Linux machine)

- Python 3.11+.
- That's it for umu-launcher: if `umu-run` isn't already on your `PATH`
  (distro package, AUR, etc.), `bnet-umu setup` downloads a self-contained
  copy automatically from
  [umu-launcher's GitHub releases](https://github.com/Open-Wine-Components/umu-launcher/releases)
  (the `-zipapp.tar` asset) into `~/.local/share/bnet-umu/umu/` and uses that.
  A system install, if present, always takes priority. umu-launcher is
  GPL-3.0-licensed; we only ever invoke it as a subprocess, and this fetches
  the official upstream binary directly rather than vendoring it in this repo.
- Optional: `xdotool`, for hands-free setup (see below). Without it, setup
  falls back to asking you to click through the installer manually.

## Install

Most distros (Arch, Fedora, Debian/Ubuntu included) mark the system Python as
"externally managed" (PEP 668), so a plain `pip install --user .` will be
refused. Use `pipx` instead — it gives this app its own isolated venv while
still putting its commands on your `PATH`:

```bash
# Arch:
sudo pacman -S --needed python-pipx
# Fedora:
sudo dnf install pipx
# Debian/Ubuntu:
sudo apt install pipx

pipx install .
```

If you'd rather manage the venv yourself: `python -m venv .venv && .venv/bin/pip install .`
and add `.venv/bin` to your `PATH` (or invoke `.venv/bin/bnet-umu` directly).

Either way, this installs two entry points:

- `bnet-umu` — CLI (`status`, `setup`, `launch`, `repair`, `open-saves`)
- `bnet-umu-gui` — the PySide6 GUI

Optionally copy `data/bnet-umu.desktop` and `data/icon.svg` into your
`~/.local/share/applications` and icon theme so it shows up in your app menu.

## Usage

```bash
bnet-umu status        # show prefix / install state
bnet-umu setup          # create the prefix and install Battle.net
bnet-umu launch          # launch Battle.net; install Diablo II: Resurrected
                          # from inside the Battle.net client itself
bnet-umu open-saves d2r  # open the exposed save folder in your file manager
bnet-umu repair           # clear a broken Battle.net Agent and reinstall it
```

Or just run `bnet-umu-gui` for the same actions in a window.

Battle.net-Setup.exe has no silent/unattended install flag, so `setup`
drives its wizard for you via `xdotool` if it's installed (pressing through
the install screens, then closing the login window it opens when done — the
same manual "don't log in during install" Wine workaround, just automated;
login itself is never scripted). Install `xdotool` for a hands-free run:

```bash
# Arch:
sudo pacman -S xdotool
# Fedora:
sudo dnf install xdotool
# Debian/Ubuntu:
sudo apt install xdotool
```

Without it, `setup` falls back to asking you to click through the installer
yourself and close the login window when it appears — log in after setup
finishes either way.

## Where things live

- Prefix: `~/.local/share/bnet-umu/prefix` (override in Settings / config)
- Exposed folders: `~/Games/battlenet/saves/<game>` and
  `~/Games/battlenet/installs/<game>` — symlinks into the prefix, so your
  file manager and backup tools can reach them without opening the hidden
  prefix directly.
- App config: `~/.config/bnet-umu/config.toml`

## Known-uncertain details that need verifying against a real install

This was developed without a Linux/Wine environment to test against, so a
few specifics are best-effort, transcribed from Lutris's Battle.net installer
script and community reports rather than confirmed firsthand:

- The `Battle.net.config` JSON key paths in
  [`bnet_umu/core/fixups.py`](bnet_umu/core/fixups.py) (`Client.HardwareAcceleration`,
  `Client.Sound.Enabled`, `Client.Streaming.Enabled`) — Blizzard doesn't
  document this schema and it can change between client versions.
  Verify against an actual `Battle.net.config` file after first install (typically
  under `drive_c/users/steamuser/AppData/Roaming/Battle.net/`) and adjust
  `BATTLENET_CONFIG_TWEAKS` if the keys don't match.
- The `steamuser` Wine username assumption used to locate that config file
  and in [`bnet_umu/core/games.py`](bnet_umu/core/games.py)'s save-folder glob.
- Diablo II: Resurrected's exact save/install folder names
  (`bnet_umu/core/games.py`'s `install_glob`/`save_glob`) — confirm against a
  real install and adjust the glob if needed.
- The installer/login window titles in
  [`bnet_umu/core/ui_automation.py`](bnet_umu/core/ui_automation.py)
  (`INSTALLER_WINDOW_TITLE`, `LOGIN_WINDOW_TITLE`) — if `xdotool` can't find
  them, setup logs that and falls back to the manual flow rather than
  hanging, but the titles themselves need confirming against a real install.

Everything else (env var handling, prefix/config logic, folder exposure,
repair) is covered by the test suite (`pytest`) and runs correctly
independent of these details.

## Possible future automation

Once Battle.net is installed and you've logged in once, actually installing
a game (Diablo II: Resurrected itself) still means clicking "Install" in the
Battle.net library UI — not automated here. A separate tool,
[barncastle/Battle.Net-Installer](https://github.com/barncastle/Battle.Net-Installer),
can trigger game install/update/repair through the local Battle.net Agent by
TACT product code (D2R's is `osi`) without touching the GUI at all, so this
could plausibly be scripted too. Not integrated yet — its window-free CLI
flow would need verifying under Wine (it's a self-contained ~15MB .NET 8
exe, so it likely doesn't need a separate .NET runtime installed in the
prefix, but that's unconfirmed), and it ships with no license file, so —
same as umu-launcher — it'd be fetched from its own GitHub release at setup
time rather than vendored here.

## Adding another game

Add an entry to `GAMES` in
[`bnet_umu/core/games.py`](bnet_umu/core/games.py) with its install/save glob
patterns — the setup/launch/repair/folder-exposure logic is game-agnostic.
