"""Settings dialog: prefix location, external folder root, GE-Proton version."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)

from ..config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.config = config

        self.prefix_edit = QLineEdit(str(config.prefix_path))
        self.external_root_edit = QLineEdit(str(config.external_root))
        self.proton_path_edit = QLineEdit(config.proton_path)
        self.proton_path_edit.setPlaceholderText(
            '"GE-Proton" tracks the latest release automatically'
        )

        form = QFormLayout()
        form.addRow("Wine prefix:", self.prefix_edit)
        form.addRow("Exposed folders root:", self.external_root_edit)
        form.addRow("Proton version:", self.proton_path_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow(form)
        layout.addRow(buttons)

    def updated_config(self) -> AppConfig:
        self.config.prefix_path = Path(self.prefix_edit.text())
        self.config.external_root = Path(self.external_root_edit.text())
        self.config.proton_path = self.proton_path_edit.text() or "GE-Proton"
        return self.config
