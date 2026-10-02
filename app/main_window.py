"""メインウィンドウ。"""

from __future__ import annotations

import json
import sqlite3

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from app import db, export_flow, fetcher
from app.workers import FetchWorker

LIST_COLUMNS = [
    "Product ID", "Original", "Orbit", "Center Lat", "Center Lon",
    "Resolution", "Pixel Width", "Pixel Height",
    "Incidence", "Emission", "Phase", "Slew", "Tags",
]
TAG_OVERLAY_ALPHA = 70  # 行に重ねるタグ色の濃さ (0-255)
LIST_KEYS = [
    "product_id", "original_product", "orbit_number", "center_latitude",
    "center_longitude", "resolution", "scaled_pixel_width", "scaled_pixel_height",
    "incidence_angle", "emission_angle", "phase_angle", "slew_angle",
]
DETAIL_GROUPS = [
    ("基本情報", ["Product", "Original product", "Pds dataset name",
                  "Target name", "Orbit number", "Start time", "Stop time",
                  "Source URL"]),
    ("観測ジオメトリ", ["Center latitude", "Center longitude", "Resolution",
                        "Incidence angle", "Emission angle", "Phase angle",
                        "Slew angle", "Spacecraft altitude"]),
    ("画像・その他", ["Image lines", "Line samples", "Sample bits",
                      "Product version", "Data quality"]),
]


class MainWindow(QMainWindow):
    def __init__(self, db_path, parent=None, settings=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NAC QuickMap")
        self.resize(1280, 800)
        self.settings = settings if settings is not None else QSettings(
            "NACQuickMap", "NACQuickMap")
        self.conn = db.connect(db_path)
        self._visible: list[dict] = []
        self._fetch_worker: FetchWorker | None = None
        self._tag_tables: dict[str, QTableWidget] = {}
        self._current_tag: str | None = None
        self._selected_tags: list[str] = []
        self._match_all = True
        self._tag_colors: dict[str, str] = {}
        self._session_start_ts = db.get_now(self.conn)
        self._build_ui()
        self._build_menu()
        self._refresh_tags()
        self._refresh_list()

    # --- UI 構築 ------------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

    def _build_left(self) -> QWidget:
        layout = QVBoxLayout()

        fetch_group = QGroupBox("自動取得（URL）")
        fetch_layout = QVBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://data.lroc.im-ldi.com/lroc/view_lroc/<dataset>/<product>")
        self.fetch_btn = QPushButton("自動取得")
        self.fetch_btn.clicked.connect(lambda _checked=False: self._on_fetch())
        fetch_layout.addWidget(self.url_edit)
        fetch_layout.addWidget(self.fetch_btn)
        fetch_group.setLayout(fetch_layout)
        layout.addWidget(fetch_group)

        tag_group = QGroupBox("タグ")
        tag_layout = QVBoxLayout()
        self.tag_list = QWidget()
        self.tag_list_layout = QVBoxLayout()
        self.tag_list_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_list.setLayout(self.tag_list_layout)
        tag_layout.addWidget(self.tag_list)

        match_layout = QHBoxLayout()
        self.match_all_check = QCheckBox("すべて一致")
        self.match_all_check.setChecked(True)
        self.match_all_check.stateChanged.connect(self._on_match_mode_changed)
        match_layout.addWidget(self.match_all_check)
        tag_layout.addLayout(match_layout)

        tag_bar = QHBoxLayout()
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("新しいタグ名")
        self.tag_edit.returnPressed.connect(self._on_add_tag)
        self.add_tag_btn = QPushButton("タグ追加")
        self.add_tag_btn.clicked.connect(lambda _checked=False: self._on_add_tag())
        tag_bar.addWidget(self.tag_edit)
        tag_bar.addWidget(self.add_tag_btn)
        tag_layout.addLayout(tag_bar)
        tag_group.setLayout(tag_layout)
        layout.addWidget(tag_group)

        list_group = QGroupBox("登録一覧")
        list_layout = QVBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Product ID / Original / Orbit で絞り込み")
        self.filter_edit.textChanged.connect(lambda _text="": self._refresh_list())
        list_layout.addWidget(self.filter_edit)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        list_layout.addWidget(self.tab_widget, 1)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)

        container = QWidget()
        container.setLayout(layout)
        return container

    def _build_right(self) -> QWidget:
        layout = QVBoxLayout()
        self.detail_tree = QTreeWidget()
        self.detail_tree.setColumnCount(2)
        self.detail_tree.setHeaderLabels(["項目", "値"])
        self.detail_tree.setAlternatingRowColors(True)
        layout.addWidget(self.detail_tree)
        container = QWidget()
        container.setLayout(layout)
        return container

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("ファイル")
        export_action = QAction("Excelにエクスポート", self)
        export_action.triggered.connect(lambda _checked=False: self._export())
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        tag_menu = self.menuBar().addMenu("タグ")
        assign_action = QAction("タグを追加", self)
        assign_action.triggered.connect(lambda _checked=False: self._on_assign_tag())
        tag_menu.addAction(assign_action)
        remove_action = QAction("タグを削除", self)
        remove_action.triggered.connect(lambda _checked=False: self._on_remove_tag())
        tag_menu.addAction(rename_action := QAction("タグ名を変更", self))
        rename_action.triggered.connect(lambda _checked=False: self._on_rename_tag())
        color_action = QAction("タグの色を変更", self)
        color_action.triggered.connect(lambda _checked=False: self._on_change_tag_color())
        tag_menu.addAction(color_action)

    # --- 一覧 ---------------------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        return self._tag_tables.get(self._tab_key())

    def _tab_key(self) -> str:
        """表示中タブの種別。"__all__" / "__session__" / タグ名。タブ名ではなくウィジェットで判定する。"""
        widget = self.tab_widget.currentWidget()
        for key, table in self._tag_tables.items():
            if table is widget:
                return key
        return "__all__"

    def _refresh_tags(self) -> None:
        db.ensure_tag_colors(self.conn)
        tags = db.list_tags(self.conn)
        self._tag_colors = {t["name"]: t["color"] for t in tags}
        # 再構築前に表示中のタブを覚えておき、可能なら同じタブに戻す
        prev_key = self._tab_key() if self.tab_widget.count() > 0 else "__session__"
        self.tab_widget.blockSignals(True)
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        self._tag_tables.clear()
        all_table = self._create_table()
        self._tag_tables["__all__"] = all_table
        self.tab_widget.addTab(all_table, "すべて")
        session_table = self._create_table()
        self._tag_tables["__session__"] = session_table
        self.tab_widget.addTab(session_table, "セッション")
        for tag in tags:
            table = self._create_table()
            self._tag_tables[tag["name"]] = table
            index = self.tab_widget.addTab(table, f"{tag['name']} ({tag['product_count']})")
            self.tab_widget.tabBar().setTabTextColor(index, QColor(tag["color"]))
        self.tab_widget.blockSignals(False)
        self._current_tag = None
        target = self._tag_tables.get(prev_key)
        if target is None:
            target = self._tag_tables["__session__"]
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(target))

        while self.tag_list_layout.count() > 0:
            item = self.tag_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for tag in tags:
            checkbox = QCheckBox(f"{tag['name']} ({tag['product_count']})")
            checkbox.setChecked(tag["name"] in self._selected_tags)
            checkbox.setStyleSheet(
                f"QCheckBox {{ border-left: 6px solid {tag['color']}; padding-left: 4px; }}")
            checkbox.stateChanged.connect(
                lambda state, name=tag["name"]: self._on_tag_check_changed(name, state))
            self.tag_list_layout.addWidget(checkbox)
        self.tag_list_layout.addStretch()

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, len(LIST_COLUMNS))
        table.setHorizontalHeaderLabels(LIST_COLUMNS)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.itemSelectionChanged.connect(self._on_selection_changed)
        return table

    def _refresh_list(self, select: str | None = None) -> None:
        if self._selected_tags:
            self._visible = db.list_products_by_tags(
                self.conn, self._selected_tags, self.filter_edit.text(),
                match_all=self._match_all)
        else:
            key = self._tab_key()
            if key == "__session__":
                self._visible = db.list_products_since(
                    self.conn, self._session_start_ts, self.filter_edit.text())
            elif key == "__all__":
                self._visible = db.list_products(self.conn, self.filter_edit.text())
            else:
                self._visible = db.list_products_by_tag(
                    self.conn, key, self.filter_edit.text())
        table = self.table
        if table is None:
            return
        table.blockSignals(True)
        table.setRowCount(len(self._visible))
        tag_map = db.list_product_tags_map(self.conn)
        for row, record in enumerate(self._visible):
            tags = tag_map.get(record.get("product_id"), [])
            overlay = self._overlay_brush(tags)
            for column, key in enumerate(LIST_KEYS):
                value = record.get(key)
                item = QTableWidgetItem("" if value is None else str(value))
                if value is None:
                    item.setForeground(QBrush(QColor(150, 150, 150)))
                if overlay is not None:
                    item.setBackground(overlay)
                table.setItem(row, column, item)
            tag_item = QTableWidgetItem(", ".join(tags))
            tag_item.setToolTip("\n".join(tags))
            if overlay is not None:
                tag_item.setBackground(overlay)
            table.setItem(row, len(LIST_KEYS), tag_item)
        table.blockSignals(False)
        if select:
            for row, record in enumerate(self._visible):
                if record.get("product_id") == select:
                    table.selectRow(row)
                    break
        self._on_selection_changed()

    def _overlay_brush(self, tags: list[str]) -> QBrush | None:
        """製品のタグ色を行に重ねるブラシ。複数タグなら名前順で最初のタグの色。"""
        for name in tags:
            color = self._tag_colors.get(name)
            if color:
                overlay = QColor(color)
                overlay.setAlpha(TAG_OVERLAY_ALPHA)
                return QBrush(overlay)
        return None

    def _current_record(self) -> dict | None:
        records = self._selected_records()
        return records[0] if records else None

    def _selected_records(self) -> list[dict]:
        model = self.table.selectionModel()
        if model is None:
            return []
        rows = sorted(index.row() for index in model.selectedRows())
        return [self._visible[row] for row in rows if 0 <= row < len(self._visible)]

    def _on_selection_changed(self) -> None:
        record = self._current_record()
        if record is None:
            self.detail_tree.clear()
            return
        self._show_detail(record)

    def _show_detail(self, record: dict) -> None:
        try:
            raw = json.loads(record.get("raw_metadata_json") or "{}")
        except json.JSONDecodeError:
            raw = {}
        self.detail_tree.clear()
        used: set[str] = set()
        for title, labels in DETAIL_GROUPS:
            group = QTreeWidgetItem([title, ""])
            self.detail_tree.addTopLevelItem(group)
            for label in labels:
                value = raw.get(label)
                if value in (None, ""):
                    field = fetcher.KEY_TO_FIELD.get(label)
                    value = record.get(field) if field else None
                text = str(value) if value not in (None, "") else "—"
                group.addChild(QTreeWidgetItem([label, text]))
                used.add(label)
            group.setExpanded(True)
        extra = QTreeWidgetItem(["その他（raw）", ""])
        self.detail_tree.addTopLevelItem(extra)
        for key in sorted(key for key in raw if key not in used):
            extra.addChild(QTreeWidgetItem([key, str(raw[key])]))
        self.detail_tree.resizeColumnToContents(0)

    # --- タグ ---------------------------------------------------------------

    def _on_tag_check_changed(self, tag_name: str, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            if tag_name not in self._selected_tags:
                self._selected_tags.append(tag_name)
        else:
            if tag_name in self._selected_tags:
                self._selected_tags.remove(tag_name)
        self._refresh_list()

    def _on_match_mode_changed(self, state: int) -> None:
        self._match_all = state == Qt.CheckState.Checked.value
        self._refresh_list()

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            self._current_tag = None
            return
        key = self._tab_key()
        self._current_tag = None if key in ("__all__", "__session__") else key
        self._refresh_list()

    def _on_tab_close_requested(self, index: int) -> None:
        if index <= 1:  # 「すべて」「セッション」は閉じられない
            return
        title = self.tab_widget.tabText(index)
        tag_name = title.split(" (")[0]
        answer = QMessageBox.question(
            self, "タグ削除",
            f"タグ '{tag_name}' を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        db.delete_tag(self.conn, tag_name)
        self._refresh_tags()
        self._refresh_list()

    def _on_add_tag(self) -> None:
        name = self.tag_edit.text().strip()
        if not name:
            return
        existing = {t["name"] for t in db.list_tags(self.conn)}
        if name in existing:
            QMessageBox.warning(self, "タグ追加", f"タグ '{name}' は既に存在します。")
            return
        db.add_tag_to_product(self.conn, "", name)
        self.tag_edit.clear()
        self._refresh_tags()
        self._refresh_list()

    def _on_delete_tag(self) -> None:
        record = self._current_record()
        if record is None:
            return
        tags = db.get_product_tags(self.conn, record["product_id"])
        if not tags:
            QMessageBox.information(self, "タグ削除", "この製品にはタグがありません。")
            return
        tag, ok = QInputDialog.getItem(
            self, "タグ削除", "削除するタグを選択:", tags, 0, False)
        if not ok:
            return
        db.remove_tag_from_product(self.conn, record["product_id"], tag)
        self._refresh_tags()
        self._refresh_list()

    def _on_rename_tag(self) -> None:
        record = self._current_record()
        if record is None:
            return
        tags = db.get_product_tags(self.conn, record["product_id"])
        if not tags:
            QMessageBox.information(self, "タグ名変更", "この製品にはタグがありません。")
            return
        old_name, ok = QInputDialog.getItem(
            self, "タグ名変更", "変更するタグを選択:", tags, 0, False)
        if not ok:
            return
        new_name, ok = QInputDialog.getText(
            self, "タグ名変更", "新しいタグ名:", text=old_name)
        if not ok:
            return
        try:
            db.rename_tag(self.conn, old_name, new_name.strip())
        except ValueError as exc:
            QMessageBox.warning(self, "タグ名変更", str(exc))
            return
        self._refresh_tags()
        self._refresh_list()

    def _on_change_tag_color(self) -> None:
        names = sorted(self._tag_colors, key=str.lower)
        if not names:
            QMessageBox.information(self, "タグの色", "タグがありません。")
            return
        name, ok = QInputDialog.getItem(
            self, "タグの色", "色を変更するタグ:", names, 0, False)
        if not ok:
            return
        color = QColorDialog.getColor(
            QColor(self._tag_colors[name]), self, f"タグ '{name}' の色")
        if not color.isValid():
            return
        db.set_tag_color(self.conn, name, color.name())
        self._refresh_tags()
        self._refresh_list()

    def _on_assign_tag(self) -> None:
        records = self._selected_records()
        if not records:
            return
        existing = {t["name"] for t in db.list_tags(self.conn)}
        tag, ok = QInputDialog.getText(
            self, "タグ追加", "タグ名（新規作成も可}:")
        if not ok:
            return
        name = tag.strip()
        if not name:
            return
        if name not in existing:
            db.add_tag_to_product(self.conn, "", name)
        for record in records:
            db.add_tag_to_product(self.conn, record["product_id"], name)
        self._refresh_tags()
        self._refresh_list()

    def _on_remove_tag(self) -> None:
        records = self._selected_records()
        if not records:
            return
        all_tags: set[str] = set()
        for record in records:
            all_tags.update(db.get_product_tags(self.conn, record["product_id"]))
        if not all_tags:
            QMessageBox.information(self, "タグ削除", "選択した製品にはタグがありません。")
            return
        tags = sorted(all_tags)
        tag, ok = QInputDialog.getItem(
            self, "タグ削除", "削除するタグを選択:", tags, 0, False)
        if not ok:
            return
        for record in records:
            db.remove_tag_from_product(self.conn, record["product_id"], tag)
        self._refresh_tags()
        self._refresh_list()

    # --- 取得 ---------------------------------------------------------------

    def _on_fetch(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "自動取得", "URLを入力してください。")
            return
        try:
            fetcher.parse_product_url(url)
        except ValueError as exc:
            QMessageBox.warning(self, "自動取得", str(exc))
            return
        self.fetch_btn.setEnabled(False)
        self.statusBar().showMessage("メタデータを取得中…")
        self._fetch_worker = FetchWorker(url)
        self._fetch_worker.succeeded.connect(self._on_fetch_done)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        self._fetch_worker.start()

    def _on_fetch_done(self, data: dict) -> None:
        self.fetch_btn.setEnabled(True)
        try:
            db.upsert_product(self.conn, data)
        except Exception as exc:  # 保存失敗は UI を止めない
            QMessageBox.warning(self, "保存エラー", str(exc))
            return
        product_id = data.get("product_id")
        self.url_edit.clear()
        self._current_tag = None
        self.tab_widget.setCurrentIndex(1)  # セッションタブへ (切替時に一度 refresh される)
        self._refresh_list(select=product_id)
        self.statusBar().showMessage(f"登録しました: {product_id}", 5000)

    def _on_fetch_failed(self, message: str) -> None:
        self.fetch_btn.setEnabled(True)
        QMessageBox.warning(self, "自動取得", message)
        self.statusBar().showMessage("取得に失敗しました", 5000)

    # --- エクスポート -------------------------------------------------------

    def _records_for_scope(self, scope: str) -> list[dict]:
        if scope == "selection":
            return self._selected_records()
        if scope == "filtered":
            return list(self._visible)
        return db.list_products(self.conn)

    def _export(self) -> None:
        scopes = export_flow.resolve_scopes(
            bool(self._selected_records()),
            bool(self.filter_edit.text().strip()))
        scope = export_flow.choose_scope(self, scopes)
        if scope is None:
            return
        records = self._records_for_scope(scope)
        if not records:
            QMessageBox.warning(self, "エクスポート", "書き出す対象がありません。")
            return
        if export_flow.export_records(self, self.settings, records):
            self.statusBar().showMessage("Excelに書き出しました", 5000)

    # --- 終了 ---------------------------------------------------------------

    def closeEvent(self, event) -> None:
        try:
            self.tab_widget.removeTab(0)
        except Exception:
            pass
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
        super().closeEvent(event)