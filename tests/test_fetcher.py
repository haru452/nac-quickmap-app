from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from app import fetcher

FIXTURE = Path(__file__).parent / "fixtures" / "product_page.html"
HTML = FIXTURE.read_text(encoding="utf-8")
VALID_URL = ("https://data.lroc.im-ldi.com/lroc/view_lroc/"
             "LRO-L-LROC-3-CDR-V1.0/M190737496RC")


class ParseProductUrlTest(unittest.TestCase):
    def test_accepts_data_host(self):
        dataset, product = fetcher.parse_product_url(VALID_URL)
        self.assertEqual(dataset, "LRO-L-LROC-3-CDR-V1.0")
        self.assertEqual(product, "M190737496RC")

    def test_accepts_wms_host_with_trailing_slash(self):
        url = "https://wms.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-2-EDR-V1.0/M1R/"
        self.assertEqual(fetcher.parse_product_url(url),
                         ("LRO-L-LROC-2-EDR-V1.0", "M1R"))

    def test_accepts_http_scheme(self):
        url = "http://data.lroc.im-ldi.com/lroc/view_lroc/DS/PR"
        self.assertEqual(fetcher.parse_product_url(url), ("DS", "PR"))

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(fetcher.parse_product_url("  " + VALID_URL + "  ")[1],
                         "M190737496RC")

    def test_rejects_other_path(self):
        with self.assertRaises(ValueError):
            fetcher.parse_product_url("https://data.lroc.im-ldi.com/lroc/search")

    def test_rejects_other_host(self):
        with self.assertRaises(ValueError):
            fetcher.parse_product_url("https://example.com/lroc/view_lroc/DS/PR")

    def test_rejects_garbage(self):
        for value in ("", "not a url", None,
                      "ftp://data.lroc.im-ldi.com/lroc/view_lroc/DS/PR"):
            with self.assertRaises(ValueError):
                fetcher.parse_product_url(value)


class SplitRowsTest(unittest.TestCase):
    def test_reads_label_value_pairs_from_fixture(self):
        rows = dict(fetcher.split_rows(HTML))
        self.assertEqual(rows["Product"], "M190737496RE")
        self.assertEqual(rows["Original product"], "nacr00098809")
        self.assertEqual(rows["Slew angle"], "0.012741557399709086")

    def test_skips_colspan_download_row(self):
        labels = [label for label, _ in fetcher.split_rows(HTML)]
        self.assertNotIn("Download EDR", labels)
        self.assertNotIn("Download CDR", labels)

    def test_tolerates_mismatched_closing_tags(self):
        html = "<table><tr><td>Product</th><td>ABC</td></tr></table>"
        self.assertEqual(fetcher.split_rows(html), [("Product", "ABC")])

    def test_keeps_blank_value(self):
        rows = dict(fetcher.split_rows(HTML))
        self.assertEqual(rows["Scaled pixel height"], "")

    def test_returns_empty_list_when_no_table(self):
        self.assertEqual(fetcher.split_rows("<html><body></body></html>"), [])
        self.assertEqual(fetcher.split_rows(""), [])


class MapColumnsTest(unittest.TestCase):
    def test_maps_and_converts_types(self):
        kv = dict(fetcher.split_rows(HTML))
        row = fetcher.map_columns(kv)
        self.assertEqual(row["product_id"], "M190737496RE")
        self.assertEqual(row["original_product"], "nacr00098809")
        self.assertEqual(row["target_name"], "MOON")
        self.assertEqual(row["orbit_number"], 13151)
        self.assertIsInstance(row["orbit_number"], int)
        self.assertAlmostEqual(row["center_latitude"], -0.3)
        self.assertAlmostEqual(row["resolution"], 0.9408832674492926)
        self.assertAlmostEqual(row["scaled_pixel_width"], 1.1)
        self.assertIsNone(row["scaled_pixel_height"])
        self.assertAlmostEqual(row["incidence_angle"], 45.78)
        self.assertAlmostEqual(row["emission_angle"], 1.18)
        self.assertAlmostEqual(row["phase_angle"], 44.6)
        self.assertAlmostEqual(row["slew_angle"], 0.012741557399709086)

    def test_all_columns_present_even_when_absent_from_page(self):
        row = fetcher.map_columns({"Product": "ABC"})
        expected = {"product_id", "original_product", "target_name", "orbit_number",
                    "center_latitude", "center_longitude", "resolution",
                    "scaled_pixel_width", "scaled_pixel_height",
                    "incidence_angle", "emission_angle", "phase_angle",
                    "slew_angle", "raw"}
        self.assertTrue(expected.issubset(row))
        self.assertEqual(row["product_id"], "ABC")
        self.assertIsNone(row["slew_angle"])

    def test_blank_values_become_none_not_zero(self):
        row = fetcher.map_columns({"Product": "ABC", "Resolution": " ",
                                   "Incidence angle": "", "Orbit number": "n/a"})
        self.assertIsNone(row["resolution"])
        self.assertIsNone(row["incidence_angle"])
        self.assertIsNone(row["orbit_number"])

    def test_unmapped_keys_only_live_in_raw(self):
        row = fetcher.map_columns({"Product": "ABC", "Scaled pixel height": "0.78"})
        self.assertNotIn("Scaled pixel height", row)
        self.assertEqual(row["raw"]["Scaled pixel height"], "0.78")


class FetchMetadataTest(unittest.TestCase):
    @staticmethod
    def _response(status=200, text=HTML, encoding="utf-8"):
        response = mock.Mock()
        response.status_code = status
        response.text = text
        response.encoding = encoding
        return response

    @mock.patch("app.fetcher.requests.get")
    def test_success(self, get):
        get.return_value = self._response()
        data = fetcher.fetch_metadata(VALID_URL)
        self.assertEqual(data["product_id"], "M190737496RE")
        self.assertEqual(data["dataset"], "LRO-L-LROC-3-CDR-V1.0")
        self.assertEqual(data["source_url"], VALID_URL)
        self.assertEqual(data["orbit_number"], 13151)
        self.assertAlmostEqual(data["slew_angle"], 0.012741557399709086)
        self.assertAlmostEqual(data["scaled_pixel_width"], 1.1)
        self.assertIsNone(data["scaled_pixel_height"])
        self.assertEqual(data["raw"]["Scaled pixel height"], "")
        get.assert_called_once()

    @mock.patch("app.fetcher.requests.get")
    def test_http_error(self, get):
        get.return_value = self._response(status=404, text="missing")
        with self.assertRaises(fetcher.FetchError) as ctx:
            fetcher.fetch_metadata(VALID_URL)
        self.assertIn("404", str(ctx.exception))

    @mock.patch("app.fetcher.requests.get")
    def test_timeout(self, get):
        get.side_effect = fetcher.requests.exceptions.Timeout()
        with self.assertRaises(fetcher.FetchError) as ctx:
            fetcher.fetch_metadata(VALID_URL)
        self.assertIn("タイムアウト", str(ctx.exception))

    @mock.patch("app.fetcher.requests.get")
    def test_connection_error(self, get):
        get.side_effect = fetcher.requests.exceptions.ConnectionError("boom")
        with self.assertRaises(fetcher.FetchError) as ctx:
            fetcher.fetch_metadata(VALID_URL)
        self.assertIn("通信エラー", str(ctx.exception))

    @mock.patch("app.fetcher.requests.get")
    def test_page_without_table(self, get):
        get.return_value = self._response(text="<html><body>nothing</body></html>")
        with self.assertRaises(fetcher.FetchError) as ctx:
            fetcher.fetch_metadata(VALID_URL)
        self.assertIn("解析", str(ctx.exception))

    @mock.patch("app.fetcher.requests.get")
    def test_page_without_product_label(self, get):
        get.return_value = self._response(
            text="<table><tr><td>Orbit number</td><td>1</td></tr></table>")
        with self.assertRaises(fetcher.FetchError) as ctx:
            fetcher.fetch_metadata(VALID_URL)
        self.assertIn("Product", str(ctx.exception))

    @mock.patch("app.fetcher.requests.get")
    def test_invalid_url_never_calls_network(self, get):
        with self.assertRaises(ValueError):
            fetcher.fetch_metadata("https://example.com/lroc/view_lroc/DS/PR")
        get.assert_not_called()
