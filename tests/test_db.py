from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import db

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
    "source_url": "https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-3-CDR-V1.0/M190737496RC",
    "raw": {"Product": "M190737496RE", "Scaled pixel height": ""},
}


class DbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "lroc_data.db"
        self.conn = db.connect(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_upsert_then_list_roundtrip(self):
        db.upsert_product(self.conn, ROW)
        rows = db.list_products(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_id"], "M190737496RE")
        self.assertEqual(rows[0]["orbit_number"], 13151)
        self.assertAlmostEqual(rows[0]["slew_angle"], 0.012741557399709086)
        self.assertAlmostEqual(rows[0]["scaled_pixel_width"], 1.1)
        self.assertAlmostEqual(rows[0]["scaled_pixel_height"], 0.78)
        self.assertEqual(rows[0]["source_url"], ROW["source_url"])
        self.assertIn("Scaled pixel height", rows[0]["raw_metadata_json"])
        self.assertIsNotNone(rows[0]["created_at"])

    def test_upsert_is_idempotent_and_updates_values(self):
        db.upsert_product(self.conn, ROW)
        db.upsert_product(self.conn, {**ROW, "orbit_number": 4242})
        rows = db.list_products(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["orbit_number"], 4242)

    def test_image_path_column_does_not_exist(self):
        db.upsert_product(self.conn, ROW)
        row = db.get_product(self.conn, "M190737496RE")
        self.assertNotIn("image_path", row)

    def test_missing_numeric_stored_as_null(self):
        db.upsert_product(self.conn, {"product_id": "ONLY", "raw": {}})
        row = db.get_product(self.conn, "ONLY")
        self.assertIsNone(row["resolution"])
        self.assertIsNone(row["scaled_pixel_width"])
        self.assertIsNone(row["scaled_pixel_height"])
        self.assertIsNone(row["slew_angle"])
        self.assertIsNone(row["orbit_number"])

    def test_filter_by_product_id(self):
        db.upsert_product(self.conn, ROW)
        db.upsert_product(self.conn, {**ROW, "product_id": "M222222222RE",
                                      "orbit_number": 4242})
        self.assertEqual(len(db.list_products(self.conn, "M1907")), 1)
        self.assertEqual(len(db.list_products(self.conn, "M2222")), 1)

    def test_filter_by_original_product(self):
        db.upsert_product(self.conn, ROW)
        self.assertEqual(len(db.list_products(self.conn, "nacr000")), 1)

    def test_filter_by_orbit_number(self):
        db.upsert_product(self.conn, ROW)
        self.assertEqual(len(db.list_products(self.conn, "13151")), 1)
        self.assertEqual(len(db.list_products(self.conn, "99999")), 0)

    def test_get_missing_product_returns_none(self):
        self.assertIsNone(db.get_product(self.conn, "NOPE"))

    def test_schema_is_idempotent(self):
        db.init_schema(self.conn)
        db.init_schema(self.conn)
        db.upsert_product(self.conn, ROW)
        self.assertEqual(len(db.list_products(self.conn)), 1)

    def test_upsert_requires_product_id(self):
        with self.assertRaises(ValueError):
            db.upsert_product(self.conn, {"raw": {}})

    def test_database_file_is_created_on_disk(self):
        self.assertTrue(self.path.exists())
