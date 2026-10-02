"""NAC QuickMap 起動スクリプト。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow

DEFAULT_DB = Path(__file__).with_name("lroc_data.db")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NAC QuickMap")
    app.setOrganizationName("NACQuickMap")
    window = MainWindow(db_path=DEFAULT_DB)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
