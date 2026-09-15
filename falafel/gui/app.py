"""GUI entry point (`falafel-gui`)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..core.prefix import migrate_legacy_data_dir
from .main_window import MainWindow


def main() -> int:
    migrate_legacy_data_dir(log=print)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
