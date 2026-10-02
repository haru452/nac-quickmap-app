"""Excel エクスポート時のダイアログフロー。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app import excel

SCOPE_LABELS = {"selection": "選択した行", "filtered": "フィルタ結果", "all": "すべて"}


def resolve_scopes(has_selection: bool, has_filter: bool) -> list[str]:
    scopes: list[str] = []
    if has_selection:
        scopes.append("selection")
    if has_filter:
        scopes.append("filtered")
    scopes.append("all")
    return scopes


def choose_scope(parent: QWidget | None, scopes: Sequence[str]) -> str | None:
    if len(scopes) == 1:
        return scopes[0]
    box = QMessageBox(parent)
    box.setWindowTitle("エクスポート範囲")
    box.setText("書き出す範囲を選んでください。")
    buttons: dict[Any, str] = {}
    for scope in scopes:
        button = box.addButton(SCOPE_LABELS[scope], QMessageBox.ButtonRole.AcceptRole)
        buttons[button] = scope
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    return buttons.get(box.clickedButton())


def choose_path(parent: QWidget | None, settings: QSettings) -> str | None:
    directory = str(settings.value("export_dir", str(Path.home())))
    default_name = datetime.now().strftime("lroc_export_%Y%m%d_%H%M%S.xlsx")
    path, _selected = QFileDialog.getSaveFileName(
        parent, "Excelにエクスポート",
        str(Path(directory) / default_name),
        "Excelファイル (*.xlsx)")
    if not path:
        return None
    if not path.lower().endswith(".xlsx"):
        path += ".xlsx"
    if Path(path).exists():
        answer = QMessageBox.question(
            parent, "上書き確認", "同じファイルが存在します。上書きしますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return None
    return path


def export_records(parent: QWidget | None, settings: QSettings,
                   records: Sequence[Mapping[str, Any]]) -> bool:
    path = choose_path(parent, settings)
    if not path:
        return False
    try:
        excel.export_xlsx(records, path)
    except OSError as exc:
        QMessageBox.warning(parent, "エクスポート", f"ファイルを書き込めません:\n{exc}")
        return False
    settings.setValue("export_dir", str(Path(path).parent))
    return True
