from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import export_flow

_APP = QApplication.instance() or QApplication([])


class ResolveScopesTest(unittest.TestCase):
    def test_no_selection_no_filter(self):
        self.assertEqual(export_flow.resolve_scopes(False, False), ["all"])

    def test_selection_only(self):
        self.assertEqual(export_flow.resolve_scopes(True, False), ["selection", "all"])

    def test_filter_only(self):
        self.assertEqual(export_flow.resolve_scopes(False, True), ["filtered", "all"])

    def test_both(self):
        self.assertEqual(export_flow.resolve_scopes(True, True),
                         ["selection", "filtered", "all"])


class ChooseScopeTest(unittest.TestCase):
    def test_single_scope_returns_without_dialog(self):
        self.assertEqual(export_flow.choose_scope(None, ["all"]), "all")

    @mock.patch("app.export_flow.QMessageBox.exec")
    @mock.patch("app.export_flow.QMessageBox.clickedButton", return_value=None)
    def test_cancel_returns_none(self, _clicked, _exec):
        self.assertIsNone(export_flow.choose_scope(None, ["selection", "all"]))


class ChoosePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(
            str(Path(self.tmp.name) / "s.ini"), QSettings.Format.IniFormat)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName")
    def test_appends_xlsx_when_missing(self, get_save):
        target = str(Path(self.tmp.name) / "area")
        get_save.return_value = (target, "")
        self.assertEqual(export_flow.choose_path(None, self.settings), target + ".xlsx")

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName")
    def test_keeps_existing_xlsx(self, get_save):
        target = str(Path(self.tmp.name) / "area.XLSX")
        get_save.return_value = (target, "")
        self.assertEqual(export_flow.choose_path(None, self.settings), target)

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName", return_value=("", ""))
    def test_cancel_returns_none(self, _get_save):
        self.assertIsNone(export_flow.choose_path(None, self.settings))

    @mock.patch("app.export_flow.QFileDialog.getSaveFileName")
    def test_overwrite_declined_returns_none(self, get_save):
        target = Path(self.tmp.name) / "dup.xlsx"
        target.write_text("keep", encoding="utf-8")
        get_save.return_value = (str(target), "")
        with mock.patch("app.export_flow.QMessageBox.question",
                        return_value=QMessageBox.StandardButton.No) as question:
            self.assertIsNone(export_flow.choose_path(None, self.settings))
        self.assertTrue(question.called)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")


class ExportRecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(
            str(Path(self.tmp.name) / "s.ini"), QSettings.Format.IniFormat)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("app.export_flow.choose_path")
    def test_writes_file_and_remembers_directory(self, choose_path):
        target = Path(self.tmp.name) / "out.xlsx"
        choose_path.return_value = str(target)
        ok = export_flow.export_records(None, self.settings, [{"product_id": "X"}])
        self.assertTrue(ok)
        self.assertTrue(target.exists())
        self.assertEqual(Path(self.settings.value("export_dir")), Path(self.tmp.name))

    @mock.patch("app.export_flow.choose_path", return_value=None)
    def test_cancelled_path_returns_false(self, _choose_path):
        self.assertFalse(
            export_flow.export_records(None, self.settings, [{"product_id": "X"}]))

    @mock.patch("app.export_flow.choose_path")
    def test_unwritable_path_returns_false_and_warns(self, choose_path):
        choose_path.return_value = str(Path(self.tmp.name) / "no" / "dir.xlsx")
        with mock.patch("app.export_flow.QMessageBox.warning") as warning:
            ok = export_flow.export_records(
                None, self.settings, [{"product_id": "X"}])
        self.assertFalse(ok)
        self.assertTrue(warning.called)
