"""Main application window: status, Setup/Launch/Repair/Open Saves/Settings."""

from __future__ import annotations

import shutil
import subprocess

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config as config_module
from ..core import prefix as prefix_module
from ..core import umu_bootstrap, umu_runner
from ..core.games import GAMES
from ..core.repair import repair as run_repair
from .settings_view import SettingsDialog
from .setup_view import SetupView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battle.net (umu)")
        self.resize(560, 420)

        self.config = config_module.load()

        self.status_label = QLabel()
        self.setup_view = SetupView()
        self.setup_view.finished_ok.connect(self._on_setup_finished)

        setup_btn = QPushButton("Setup Battle.net")
        setup_btn.clicked.connect(self._on_setup_clicked)

        launch_btn = QPushButton("Launch Battle.net")
        launch_btn.clicked.connect(self._on_launch_clicked)

        repair_btn = QPushButton("Repair")
        repair_btn.clicked.connect(self._on_repair_clicked)

        open_saves_btn = QPushButton("Open Diablo II: Resurrected Saves")
        open_saves_btn.clicked.connect(self._on_open_saves_clicked)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings_clicked)

        buttons = QHBoxLayout()
        for btn in (setup_btn, launch_btn, repair_btn, open_saves_btn, settings_btn):
            buttons.addWidget(btn)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)
        layout.addWidget(self.setup_view)
        self.setCentralWidget(central)

        self._refresh_status()

    def _refresh_status(self) -> None:
        lines = [f"Prefix: {self.config.prefix_path}"]

        umu_path = umu_bootstrap.find_umu_run()
        if umu_path is None:
            lines.append(
                "umu-run: not found yet — will be downloaded automatically "
                "the first time you run Setup."
            )
        else:
            origin = "system" if shutil.which(umu_runner.UMU_BIN) == str(umu_path) else "bundled"
            lines.append(f"umu-run: found ({origin})")

        bnet_exe = prefix_module.find_battlenet_exe(self.config.prefix_path)
        lines.append(f"Battle.net installed: {'yes' if bnet_exe else 'no'}")

        d2r = GAMES["d2r"]
        installed = prefix_module.find_game_install(self.config.prefix_path, d2r)
        lines.append(f"{d2r.name} detected: {'yes' if installed else 'no'}")

        self.status_label.setText("\n".join(lines))

    def _on_setup_clicked(self) -> None:
        self.setup_view.start(self.config.prefix_path, self.config.proton_path)

    def _on_setup_finished(self, ok: bool) -> None:
        self._refresh_status()
        if not ok:
            QMessageBox.warning(
                self, "Setup", "Setup did not finish cleanly — see the log above."
            )

    def _on_launch_clicked(self) -> None:
        bnet_exe = prefix_module.find_battlenet_exe(self.config.prefix_path)
        if bnet_exe is None:
            QMessageBox.information(
                self, "Launch", "Battle.net isn't installed yet — run Setup first."
            )
            return

        umu_bin = umu_bootstrap.find_umu_run()
        if umu_bin is None:
            QMessageBox.information(
                self, "Launch", "umu-run isn't set up yet — run Setup first."
            )
            return

        invocation = umu_runner.build_invocation(
            bnet_exe,
            prefix=self.config.prefix_path,
            proton_path=self.config.proton_path,
            gameid="umu-default",
            store="battlenet",
            umu_bin=umu_bin,
        )
        umu_runner.run(invocation, background=True)

        for game in GAMES.values():
            try:
                prefix_module.expose_game_folders(
                    self.config.prefix_path, game, self.config.external_root
                )
            except FileExistsError:
                pass
        self._refresh_status()

    def _on_repair_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Repair",
            "This clears the Battle.net Agent's cached state and reinstalls "
            "it on next launch. Continue?",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = run_repair(self.config.prefix_path)
        QMessageBox.information(
            self,
            "Repair",
            f"Cleared {len(removed)} director{'y' if len(removed) == 1 else 'ies'}. "
            "Launch Battle.net to let it reinstall the Agent.",
        )
        self._refresh_status()

    def _on_open_saves_clicked(self) -> None:
        d2r = GAMES["d2r"]
        target = self.config.external_root / "saves" / d2r.external_dirname
        if not target.exists():
            QMessageBox.information(
                self,
                "Open Saves",
                "No save folder found yet — install and run the game at "
                "least once first.",
            )
            return
        subprocess.Popen(["xdg-open", str(target)])

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.updated_config()
            config_module.save(self.config)
            self._refresh_status()
