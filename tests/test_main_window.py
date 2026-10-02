from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from app import db
from app.main_window import MainWindow

_APP = QApplication.instance() or QApplication([])

URL = ("https://data.lroc.im-ldi.com/lroc/view_lroc/"
       "LRO-L-LROC-3-CDR-V1.0/M190737496RC")

ROW = {
    "product_id": "M190737496RE",
    "original_product": "nacr00098809",
    "target_name": "MOON",
    "orbit_number": 13151,
    "center_latitude": -0.3,
    "center_longitude": 339.1,
    "resolution": 0.9408832674492926,
    "scaled_pixel_width": 1.1,
    "scaled_pixel_height": 0.78,
    "incidence_angle": 45.78,
    "emission_angle": 1.18,
    "phase_angle": 44.6,
    "slew_angle": 0.012741557399709086,
    "raw": {"Product": "M190737496RE",
            "Incidence angle": "45.78",
            "Slew angle": "0.012741557399709086",
            "Scaled pixel height": "0.78"},
}

ROW2 = {**ROW, "product_id": "M222222222RE", "original_product": "nacl0000zzzz",
        "orbit_number": 4242, "raw": {"Product": "M222222222RE"}}


class MainWindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.db_path = base / "t.db"
        conn = db.connect(self.db_path)
        db.upsert_product(conn, ROW)
        db.upsert_product(conn, ROW2)
        conn.close()
        self.settings = QSettings(str(base / "s.ini"), QSettings.Format.IniFormat)
        self.win = MainWindow(db_path=self.db_path, settings=self.settings)
        self.win.show()
        _APP.processEvents()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        _APP.processEvents()
        self.tmp.cleanup()

    # --- 一覧 ---------------------------------------------------------------

    def test_table_lists_registered_rows(self):
        self.assertEqual(self.win.table.rowCount(), 2)

    def test_columns_match_spec(self):
        labels = [self.win.table.horizontalHeaderItem(i).text()
                  for i in range(self.win.table.columnCount())]
        self.assertEqual(
            labels,
            ["Product ID", "Original", "Orbit", "Center Lat", "Center Lon",
             "Resolution", "Pixel Width", "Pixel Height",
             "Incidence", "Emission", "Phase", "Slew"])

    def test_filter_by_product_id(self):
        self.win.filter_edit.setText("M1907")
        self.assertEqual(self.win.table.rowCount(), 1)

    def test_filter_by_original_product(self):
        self.win.filter_edit.setText("nacl0000")
        self.assertEqual(self.win.table.rowCount(), 1)

    def test_filter_by_orbit(self):
        self.win.filter_edit.setText("4242")
        self.assertEqual(self.win.table.rowCount(), 1)

    def test_filter_no_match(self):
        self.win.filter_edit.setText("zzz-nothing")
        self.assertEqual(self.win.table.rowCount(), 0)

    def test_selection_mode_allows_multiple(self):
        self.win.table.selectAll()
        self.assertEqual(len(self.win._selected_records()), 2)

    # --- 詳細 ---------------------------------------------------------------

    def test_selection_fills_detail_tree(self):
        self.win.table.selectRow(0)
        tree = self.win.detail_tree
        self.assertEqual(tree.topLevelItemCount(), 4)
        titles = [tree.topLevelItem(i).text(0) for i in range(4)]
        self.assertEqual(
            titles,
            ["基本情報", "観測ジオメトリ", "画像・その他", "その他（raw）"])

    def test_detail_shows_values_and_dash(self):
        self.win.table.selectRow(0)
        tree = self.win.detail_tree
        geometry = tree.topLevelItem(1)
        values = {geometry.child(i).text(0): geometry.child(i).text(1)
                  for i in range(geometry.childCount())}
        self.assertEqual(values["Incidence angle"], "45.78")
        self.assertEqual(values["Spacecraft altitude"], "—")

    def test_no_selection_clears_tree(self):
        self.win.table.clearSelection()
        self.win._on_selection_changed()
        self.assertEqual(self.win.detail_tree.topLevelItemCount(), 0)

    # --- 取得 ---------------------------------------------------------------

    def test_empty_url_warns_without_worker(self):
        self.win.url_edit.setText("   ")
        with mock.patch("app.main_window.QMessageBox.warning") as warning:
            self.win._on_fetch()
        self.assertTrue(warning.called)
        self.assertIsNone(self.win._fetch_worker)

    def test_invalid_url_warns_without_worker(self):
        self.win.url_edit.setText("https://example.com/lroc/view_lroc/DS/PR")
        with mock.patch("app.main_window.QMessageBox.warning") as warning:
            self.win._on_fetch()
        self.assertTrue(warning.called)
        self.assertIsNone(self.win._fetch_worker)

    @mock.patch("app.fetcher.fetch_metadata")
    def test_fetch_success_adds_row_and_selects_it(self, fetch):
        fetch.return_value = {**ROW, "product_id": "M333333333RE"}
        self.win.url_edit.setText(URL)
        self.win._on_fetch()
        worker = self.win._fetch_worker
        self.assertIsNotNone(worker)
        self.assertTrue(worker.wait(10000))
        for _ in range(100):
            _APP.processEvents()
            if self.win.fetch_btn.isEnabled():
                break
            time.sleep(0.02)
        self.assertTrue(self.win.fetch_btn.isEnabled())
        self.assertEqual(self.win.table.rowCount(), 3)
        self.assertEqual(self.win._current_record()["product_id"], "M333333333RE")

    def test_fetch_failed_reports_and_reenables(self):
        self.win.fetch_btn.setEnabled(False)
        with mock.patch("app.main_window.QMessageBox.warning") as warning:
            self.win._on_fetch_failed("通信エラーが発生しました")
        self.assertTrue(self.win.fetch_btn.isEnabled())
        warning.assert_called_once()

    def test_fetch_done_survives_db_error(self):
        self.win.fetch_btn.setEnabled(False)
        with mock.patch("app.db.upsert_product", side_effect=RuntimeError("boom")), \
                mock.patch("app.main_window.QMessageBox.warning") as warning:
            self.win._on_fetch_done({**ROW, "product_id": "M444444444RE"})
        warning.assert_called_once()
        self.assertTrue(self.win.fetch_btn.isEnabled())

    # --- エクスポート -------------------------------------------------------

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName")
    @mock.patch("app.export_flow.choose_scope", return_value="selection")
    def test_export_selection_writes_named_file(self, _scope, get_save):
        target = Path(self.tmp.name) / "sinus_iridum.xlsx"
        get_save.return_value = (str(target), "Excelファイル (*.xlsx)")
        self.win.table.selectRow(0)
        self.win._export()
        self.assertTrue(target.exists())

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName", return_value=("", ""))
    @mock.patch("app.export_flow.choose_scope", return_value="all")
    def test_cancelled_save_dialog_writes_nothing(self, _scope, _get_save):
        self.win._export()
        self.assertFalse((Path(self.tmp.name) / "cancelled.xlsx").exists())

    @mock.patch("app.export_flow.choose_scope", return_value="filtered")
    @mock.patch("app.main_window.QMessageBox.warning")
    def test_empty_scope_warns(self, warning, _scope):
        self.win.filter_edit.setText("zzz-nothing")
        self.win._export()
        warning.assert_called_once()

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName")
    @mock.patch("app.export_flow.choose_scope", return_value="all")
    def test_export_asks_before_overwriting(self, _scope, get_save):
        target = Path(self.tmp.name) / "dup.xlsx"
        target.write_text("keep", encoding="utf-8")
        get_save.return_value = (str(target), "")
        with mock.patch("app.export_flow.QMessageBox.question",
                        return_value=0) as question:
            self.win._export()
        self.assertTrue(question.called)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")
