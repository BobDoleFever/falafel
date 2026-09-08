"""Progress view + background worker for the Battle.net install flow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from ..core.setup_flow import run_setup


class SetupWorker(QThread):
    log = Signal(str)
    finished_ok = Signal(bool)

    def __init__(self, prefix_path: Path, proton_path: str, parent=None):
        super().__init__(parent)
        self.prefix_path = prefix_path
        self.proton_path = proton_path

    def run(self) -> None:
        try:
            ok = run_setup(self.prefix_path, self.proton_path, log=self.log.emit)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.log.emit(f"Setup failed: {exc}")
            ok = False
        self.finished_ok.emit(ok)


class SetupView(QWidget):
    finished_ok = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: SetupWorker | None = None

        layout = QVBoxLayout(self)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_view)

    def start(self, prefix_path: Path, proton_path: str) -> None:
        self.log_view.clear()
        self.progress.show()
        self._worker = SetupWorker(prefix_path, proton_path)
        self._worker.log.connect(self.log_view.appendPlainText)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, ok: bool) -> None:
        self.progress.hide()
        self.finished_ok.emit(ok)
