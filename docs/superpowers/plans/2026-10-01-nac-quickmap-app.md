# NAC QuickMap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt6 desktop app that fetches LROC product-page metadata from a pasted URL, accumulates it in a SQLite table, and exports the table to a user-named `.xlsx` file.

**Architecture:** Three Qt-free core modules (`fetcher`, `db`, `excel`) plus one Qt dialog-flow module (`export_flow`), glued together by two Qt classes: `FetchWorker` (a `QThread` that performs the HTTP fetch) and `MainWindow` (layout, list, detail tree, wiring). There is no filesystem scanning and no image handling of any kind.

**Tech Stack:** Python 3.10+ (verified runtime 3.13.15), PyQt6 6.11.0, requests, beautifulsoup4, openpyxl, sqlite3, unittest.

**Spec:** `C:\Users\haru0\club\class\nac-quickmap-app\docs\superpowers\specs\2026-10-01-nac-quickmap-app-design.md` — the plan argues from the spec; read both.

## Global Constraints

- Project root for every command: `C:\Users\haru0\club\class\nac-quickmap-app`
- The Python launcher is `py` (bare `python` is not on PATH).
- Dependencies — exactly these, no others: `PyQt6`, `requests`, `beautifulsoup4`, `openpyxl`. **`Pillow` must not be added**; there is no image handling.
- Test command for every task: `py -m unittest discover -s tests -v`
- All user-facing strings (labels, dialogs, status messages, README) are Japanese.
- `app/fetcher.py`, `app/db.py`, and `app/excel.py` must never import Qt.
- Unit tests must never touch the network: patch `app.fetcher.requests.get`.
- There must be **no** `image_path` column, no `app/scanner.py`, no `app/image_view.py`, and no folder-scan UI anywhere.
- `QThread` signal names must not collide with built-ins: use `succeeded` and `failed`, never `finished`.
- Do **not** run any `git` command. The user has not requested commits; leave the working tree as-is.
- `app/` is importable in tests because `python -m unittest` puts the cwd on `sys.path`.

---

### Task 1: Scaffold + URL/HTML parsing

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `tests/fixtures/product_page.html`
- Create: `app/fetcher.py`
- Create: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `fetcher.parse_product_url(url: str) -> tuple[str, str]` — raises `ValueError`
  - `fetcher.split_rows(html: str) -> list[tuple[str, str]]`
  - `fetcher.KEY_TO_FIELD: dict[str, str]`, `fetcher.FetchError`
  - constants `ALLOWED_HOSTS`, `USER_AGENT`, `DEFAULT_TIMEOUT`

- [ ] **Step 1: Write `requirements.txt`**

```
PyQt6>=6.5
requests>=2.31
beautifulsoup4>=4.12
openpyxl>=3.1
```

- [ ] **Step 2: Install dependencies**

Run: `py -m pip install -r requirements.txt`
Expected: succeeds; `bs4` and `openpyxl` were previously missing from this machine.

- [ ] **Step 3: Create `app/__init__.py`**

An empty file is enough.

- [ ] **Step 4: Create `tests/fixtures/product_page.html`**

A trimmed but structurally faithful copy of the real page: one `<table>`, a first row with
`colspan="2"` download links, mismatched `</th>` closers, and a blank value.

```html
<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"><title>LROC Observation M190737496R</title></head>
  <body>
    <table style="border-spacing:0">
      <tr style=background-color:white><td colspan="2">
        <ul>
          <li><a href="//pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0011/DATA/SCI/2012125/NAC/M190737496RE.IMG">Download EDR</a></li>
          <li><a href="//pds.lroc.im-ldi.com/data/LRO-L-LROC-3-CDR-V1.0/LROLRC_1011/DATA/SCI/2012125/NAC/M190737496RC.IMG">Download CDR</a></li>
        </ul>
      </td></tr>
      <tr style=background-color:white><td>Product</th><td>M190737496RE</td></tr>
      <tr style=background-color:#ddd><td>Pds dataset name</th><td>LRO-L-LROC-2-EDR-V1.0</td></tr>
      <tr style=background-color:white><td>Original product</th><td>nacr00098809</td></tr>
      <tr style=background-color:#ddd><td>Target name</th><td>MOON</td></tr>
      <tr style=background-color:white><td>Orbit number</th><td>13151</td></tr>
      <tr style=background-color:#ddd><td>Slew angle</th><td>0.012741557399709086</td></tr>
      <tr style=background-color:white><td>Resolution</th><td>0.9408832674492926</td></tr>
      <tr style=background-color:#ddd><td>Emission angle</th><td>1.18</td></tr>
      <tr style=background-color:white><td>Incidence angle</th><td>45.78</td></tr>
      <tr style=background-color:#ddd><td>Phase angle</th><td>44.6</td></tr>
      <tr style=background-color:white><td>Center latitude</th><td>-0.3</td></tr>
      <tr style=background-color:#ddd><td>Center longitude</th><td>339.1</td></tr>
      <tr style=background-color:white><td>Scaled pixel width</th><td>1.1</td></tr>
      <tr style=background-color:#ddd><td>Scaled pixel height</th><td> </td></tr>
      <tr style=background-color:white><td>Spacecraft altitude</th><td>110.72</td></tr>
    </table>
  </body>
</html>
```

- [ ] **Step 5: Write the failing tests in `tests/test_fetcher.py`**

```python
from __future__ import annotations

import unittest
from pathlib import Path

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
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: ERROR with `ModuleNotFoundError: No module named 'app.fetcher'`.

- [ ] **Step 7: Implement the parsing half of `app/fetcher.py`**

```python
"""LROC 製品ページの取得と解析。Qt には依存しない。"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

ALLOWED_HOSTS = frozenset({"data.lroc.im-ldi.com", "wms.lroc.im-ldi.com"})
USER_AGENT = "nac-quickmap-app/1.0"
DEFAULT_TIMEOUT = 20.0

_URL_RE = re.compile(
    r"^https?://(?P<host>[^/]+)/lroc/view_lroc/"
    r"(?P<dataset>[A-Za-z0-9][A-Za-z0-9.\-]*)/"
    r"(?P<product>[A-Za-z0-9][A-Za-z0-9.\-]*)/?$"
)

KEY_TO_FIELD = {
    "Product": "product_id",
    "Original product": "original_product",
    "Target name": "target_name",
    "Orbit number": "orbit_number",
    "Center latitude": "center_latitude",
    "Center longitude": "center_longitude",
    "Resolution": "resolution",
    "Scaled pixel width": "scaled_pixel_width",
    "Scaled pixel height": "scaled_pixel_height",
    "Incidence angle": "incidence_angle",
    "Emission angle": "emission_angle",
    "Phase angle": "phase_angle",
    "Slew angle": "slew_angle",
}


class FetchError(Exception):
    """ユーザーに表示できる取得・解析エラー。"""


def parse_product_url(url: str) -> tuple[str, str]:
    """URL を (dataset, product) に分解する。形式が違えば ValueError。"""
    text = (url or "").strip()
    match = _URL_RE.match(text)
    if match is None:
        raise ValueError(
            "URLの形式が正しくありません。\n"
            "https://data.lroc.im-ldi.com/lroc/view_lroc/<dataset>/<product> "
            "の形式で入力してください。"
        )
    host = match.group("host").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"対応していないホストです: {host}")
    return match.group("dataset"), match.group("product")


def split_rows(html: str) -> list[tuple[str, str]]:
    """ページ内唯一のテーブルを (ラベル, 値) のリストに変換する。"""
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    pairs: list[tuple[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) != 2:
            continue  # colspan=2 のダウンロード行をスキップ
        label = cells[0].get_text(" ", strip=True)
        value = cells[1].get_text(" ", strip=True)
        if label:
            pairs.append((label, value))
    return pairs
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all `test_fetcher` tests PASS.

---

### Task 2: Column mapping + network fetch

**Files:**
- Modify: `app/fetcher.py` (append imports and the mapping/fetch functions)
- Modify: `tests/test_fetcher.py` (append two test classes and one import)

**Interfaces:**
- Consumes: `parse_product_url`, `split_rows`, `FetchError`, `KEY_TO_FIELD`, `USER_AGENT`, `DEFAULT_TIMEOUT` from Task 1.
- Produces:
  - `fetcher.map_columns(kv: dict[str, str]) -> dict[str, Any]` — always contains every DB field plus `"raw"`
  - `fetcher.fetch_metadata(url: str, timeout: float = 20.0) -> dict[str, Any]` — raises `ValueError` for a bad URL, `FetchError` otherwise. The returned dict carries every key of `db.COLUMNS`, plus `dataset`, `source_url`, `raw`.

- [ ] **Step 1: Append the failing tests to `tests/test_fetcher.py`**

Add `from unittest import mock` to the imports, then append:

```python
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
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `py -m unittest discover -s tests -v`
Expected: `AttributeError: module 'app.fetcher' has no attribute 'map_columns'` (and the same for `fetch_metadata`).

- [ ] **Step 3: Append the implementation to `app/fetcher.py`**

Change the import block at the top to:

```python
from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup
```

Then append the following to the end of the file:

```python
TEXT_FIELDS = frozenset({"product_id", "original_product", "target_name"})
INT_FIELDS = frozenset({"orbit_number"})
REAL_FIELDS = frozenset({
    "center_latitude", "center_longitude", "resolution",
    "scaled_pixel_width", "scaled_pixel_height",
    "incidence_angle", "emission_angle", "phase_angle", "slew_angle",
})
ALL_FIELDS = tuple(TEXT_FIELDS | INT_FIELDS | REAL_FIELDS)


def _to_real(raw: Any) -> float | None:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(raw: Any) -> int | None:
    value = _to_real(raw)
    return None if value is None else int(value)


def map_columns(kv: dict[str, str]) -> dict[str, Any]:
    """(ラベル, 値) 辞書を DB 行相当の辞書に変換する。未対応キーは raw に残す。"""
    row: dict[str, Any] = {"raw": dict(kv)}
    for field in ALL_FIELDS:
        row[field] = None
    for label, field in KEY_TO_FIELD.items():
        raw = kv.get(label)
        if field in TEXT_FIELDS:
            row[field] = (raw or "").strip() or None
        elif field in INT_FIELDS:
            row[field] = _to_int(raw)
        else:
            row[field] = _to_real(raw)
    return row


def fetch_metadata(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """URL のページを取得してメタデータ辞書を返す。失敗時は FetchError。"""
    dataset, _product = parse_product_url(url)
    try:
        response = requests.get(url, timeout=timeout,
                                headers={"User-Agent": USER_AGENT})
    except requests.exceptions.Timeout as exc:
        raise FetchError("取得がタイムアウトしました。時間をおいて再度お試しください。") from exc
    except requests.exceptions.RequestException as exc:
        raise FetchError(f"通信エラーが発生しました:\n{exc}") from exc
    if response.status_code != 200:
        raise FetchError(f"取得に失敗しました (HTTP {response.status_code})。")
    if response.encoding is None:
        response.encoding = response.apparent_encoding or "utf-8"
    kv = dict(split_rows(response.text))
    if not kv:
        raise FetchError("ページからメタデータを解析できませんでした。")
    row = map_columns(kv)
    if not row.get("product_id"):
        raise FetchError("ページに Product が見つかりませんでした。")
    row["dataset"] = dataset
    row["source_url"] = url
    return row
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all tests PASS.

- [ ] **Step 5: Confirm the core module stays Qt-free**

Run: `py -c "import app.fetcher; print('ok')"`
Expected: `ok`

---

### Task 3: SQLite layer

**Files:**
- Create: `app/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: the field names produced by `fetcher.map_columns` and its `raw` key.
- Produces:
  - `db.connect(db_path: str | Path) -> sqlite3.Connection` (row factory set, schema created)
  - `db.init_schema(conn) -> None`
  - `db.COLUMNS: tuple[str, ...]` — 13 field names, **no `image_path`**
  - `db.upsert_product(conn, row: Mapping[str, Any]) -> str` (returns `product_id`; raises `ValueError` when missing)
  - `db.list_products(conn, filter_text: str = "") -> list[dict]` newest-first
  - `db.get_product(conn, product_id: str) -> dict | None`

- [ ] **Step 1: Write the failing tests in `tests/test_db.py`**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Implement `app/db.py`**

```python
"""SQLite レイヤー。Qt には依存しない。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

SCHEMA = """
CREATE TABLE IF NOT EXISTS lroc_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT UNIQUE,
    original_product TEXT,
    target_name TEXT,
    orbit_number INTEGER,
    center_latitude REAL,
    center_longitude REAL,
    resolution REAL,
    scaled_pixel_width REAL,
    scaled_pixel_height REAL,
    incidence_angle REAL,
    emission_angle REAL,
    phase_angle REAL,
    slew_angle REAL,
    raw_metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

COLUMNS: tuple[str, ...] = (
    "product_id", "original_product", "target_name", "orbit_number",
    "center_latitude", "center_longitude", "resolution",
    "scaled_pixel_width", "scaled_pixel_height",
    "incidence_angle", "emission_angle", "phase_angle", "slew_angle",
)

_SELECT = f"SELECT {', '.join(COLUMNS)}, created_at FROM lroc_products"

_UPSERT = f"""
INSERT INTO lroc_products ({', '.join(COLUMNS)}, raw_metadata_json)
VALUES ({', '.join(':' + c for c in COLUMNS)}, :raw_metadata_json)
ON CONFLICT(product_id) DO UPDATE SET
    original_product  = excluded.original_product,
    target_name       = excluded.target_name,
    orbit_number      = excluded.orbit_number,
    center_latitude   = excluded.center_latitude,
    center_longitude  = excluded.center_longitude,
    resolution        = excluded.resolution,
    scaled_pixel_width  = excluded.scaled_pixel_width,
    scaled_pixel_height = excluded.scaled_pixel_height,
    incidence_angle   = excluded.incidence_angle,
    emission_angle    = excluded.emission_angle,
    phase_angle       = excluded.phase_angle,
    slew_angle        = excluded.slew_angle,
    raw_metadata_json = excluded.raw_metadata_json,
    created_at        = CURRENT_TIMESTAMP
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_column(conn, "slew_angle", "REAL")
    _ensure_column(conn, "scaled_pixel_width", "REAL")
    _ensure_column(conn, "scaled_pixel_height", "REAL")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, name: str, type_name: str) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(lroc_products)")}
    if name not in existing:
        conn.execute(f"ALTER TABLE lroc_products ADD COLUMN {name} {type_name}")


def upsert_product(conn: sqlite3.Connection, row: Mapping[str, Any]) -> str:
    product_id = row.get("product_id")
    if not product_id:
        raise ValueError("Product が取得できませんでした。")
    values = {column: row.get(column) for column in COLUMNS}
    values["raw_metadata_json"] = json.dumps(row.get("raw") or {}, ensure_ascii=False)
    conn.execute(_UPSERT, values)
    conn.commit()
    return str(product_id)


def list_products(conn: sqlite3.Connection, filter_text: str = "") -> list[dict[str, Any]]:
    sql = _SELECT
    params: list[Any] = []
    term = (filter_text or "").strip()
    if term:
        like = f"%{term}%"
        sql += (" WHERE product_id LIKE ? OR original_product LIKE ?"
                " OR CAST(orbit_number AS TEXT) LIKE ?")
        params = [like, like, like]
    sql += " ORDER BY id DESC"
    return [dict(record) for record in conn.execute(sql, params).fetchall()]


def get_product(conn: sqlite3.Connection, product_id: str) -> dict[str, Any] | None:
    record = conn.execute(_SELECT + " WHERE product_id = ?", (product_id,)).fetchone()
    return dict(record) if record is not None else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all `test_db` tests PASS and earlier tests still PASS.

### Task 4: Excel export core

**Files:**
- Create: `app/excel.py`
- Create: `tests/test_excel.py`

**Interfaces:**
- Consumes: the record dicts produced by `db.list_products` (same key names).
- Produces: `excel.HEADERS: tuple[str, ...]`, `excel.KEYS: tuple[str, ...]`, and
  `excel.export_xlsx(records: Sequence[Mapping[str, Any]], path: str | Path) -> None`
  (raises `OSError` when the path is unwritable).

- [ ] **Step 1: Write the failing tests in `tests/test_excel.py`**

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import openpyxl

from app import excel

RECORD = {
    "product_id": "M190737496RE",
    "original_product": "nacr00098809",
    "target_name": "MOON",
    "orbit_number": 13151,
    "center_latitude": -0.3,
    "center_longitude": 339.1,
    "resolution": 0.9408832674492926,
    "scaled_pixel_width": 1.1,
    "scaled_pixel_height": 0.78,
    "slew_angle": 0.012741557399709086,
    "incidence_angle": 45.78,
    "emission_angle": 1.18,
    "phase_angle": 44.6,
    "created_at": "2026-10-01 12:00:00",
}


class ExportXlsxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out.xlsx"

    def tearDown(self):
        self.tmp.cleanup()

    def test_header_order_matches_spec(self):
        self.assertEqual(
            list(excel.HEADERS),
            ["Product ID", "Original Product", "Target", "Orbit",
             "Center Latitude", "Center Longitude", "Resolution",
             "Scaled Pixel Width", "Scaled Pixel Height", "Slew Angle",
             "Incidence Angle", "Emission Angle", "Phase Angle", "Registered At"])
        self.assertEqual(len(excel.KEYS), len(excel.HEADERS))

    def test_header_and_numeric_cells(self):
        excel.export_xlsx([RECORD], self.out)
        sheet = openpyxl.load_workbook(self.out).active
        self.assertEqual(sheet.cell(1, 1).value, "Product ID")
        self.assertEqual(sheet.cell(1, 1).font.bold, True)
        self.assertEqual(sheet.cell(2, 1).value, "M190737496RE")
        self.assertIsInstance(sheet.cell(2, 4).value, int)
        self.assertEqual(sheet.cell(2, 4).value, 13151)
        self.assertIsInstance(sheet.cell(2, 7).value, float)
        self.assertAlmostEqual(sheet.cell(2, 8).value, 1.1)
        self.assertAlmostEqual(sheet.cell(2, 9).value, 0.78)
        self.assertAlmostEqual(sheet.cell(2, 10).value, 0.012741557399709086)
        self.assertEqual(sheet.freeze_panes, "A2")

    def test_missing_values_become_blank(self):
        excel.export_xlsx([{"product_id": "X"}], self.out)
        sheet = openpyxl.load_workbook(self.out).active
        self.assertIn(sheet.cell(2, 10).value, ("", None))

    def test_no_records_writes_header_only(self):
        excel.export_xlsx([], self.out)
        sheet = openpyxl.load_workbook(self.out).active
        self.assertEqual(sheet.max_row, 1)

    def test_unwritable_path_raises_oserror(self):
        with self.assertRaises(OSError):
            excel.export_xlsx([RECORD], Path(self.tmp.name) / "missing" / "dir.xlsx")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: `ModuleNotFoundError: No module named 'app.excel'`

- [ ] **Step 3: Implement `app/excel.py`**

```python
"""Excel (.xlsx) 出力。Qt には依存しない。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

HEADERS: tuple[str, ...] = (
    "Product ID", "Original Product", "Target", "Orbit",
    "Center Latitude", "Center Longitude", "Resolution",
    "Scaled Pixel Width", "Scaled Pixel Height", "Slew Angle",
    "Incidence Angle", "Emission Angle", "Phase Angle", "Registered At",
)

KEYS: tuple[str, ...] = (
    "product_id", "original_product", "target_name", "orbit_number",
    "center_latitude", "center_longitude", "resolution",
    "scaled_pixel_width", "scaled_pixel_height", "slew_angle",
    "incidence_angle", "emission_angle", "phase_angle", "created_at",
)

WIDTHS: tuple[int, ...] = (16, 18, 10, 8, 16, 16, 12, 16, 16, 12, 16, 16, 12, 20)


def export_xlsx(records: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "LROC"
    sheet.append(list(HEADERS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for record in records:
        sheet.append([_cell(record, key) for key in KEYS])
    for index, width in enumerate(WIDTHS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    workbook.save(str(path))


def _cell(record: Mapping[str, Any], key: str) -> Any:
    value = record.get(key)
    return "" if value is None else value
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all tests PASS.

---

### Task 5: Export dialog flow

**Files:**
- Create: `app/export_flow.py`
- Create: `tests/test_export_flow.py`

**Interfaces:**
- Consumes: `excel.export_xlsx` (Task 4).
- Produces:
  - `export_flow.SCOPE_LABELS: dict[str, str]`
  - `export_flow.resolve_scopes(has_selection: bool, has_filter: bool) -> list[str]` → a subset of `["selection", "filtered", "all"]`, always ending with `"all"`
  - `export_flow.choose_scope(parent, scopes: Sequence[str]) -> str | None`
  - `export_flow.choose_path(parent, settings: QSettings) -> str | None` (returns the path with `.xlsx` appended when needed)
  - `export_flow.export_records(parent, settings: QSettings, records: Sequence[Mapping]) -> bool`

- [ ] **Step 1: Write the failing tests in `tests/test_export_flow.py`**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: `ModuleNotFoundError: No module named 'app.export_flow'`

- [ ] **Step 3: Implement `app/export_flow.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all tests PASS.

### Task 6: FetchWorker (QThread)

**Files:**
- Create: `app/workers.py`
- Create: `tests/test_workers.py`

**Interfaces:**
- Consumes: `app.fetcher.fetch_metadata` (Task 2), `app.fetcher.FetchError`.
- Produces: `workers.FetchWorker(url: str, parent=None)` with
  `succeeded = pyqtSignal(dict)`, `failed = pyqtSignal(str)`, and `run()`.

- [ ] **Step 1: Write the failing tests in `tests/test_workers.py`**

```python
from __future__ import annotations

import unittest
from unittest import mock

from app import fetcher
from app.workers import FetchWorker

VALID_URL = ("https://data.lroc.im-ldi.com/lroc/view_lroc/"
             "LRO-L-LROC-3-CDR-V1.0/M190737496RC")


class FetchWorkerTest(unittest.TestCase):
    @mock.patch("app.fetcher.fetch_metadata")
    def test_success_emits_dict(self, fetch):
        fetch.return_value = {"product_id": "M190737496RE"}
        worker = FetchWorker(VALID_URL)
        received: dict = {}
        worker.succeeded.connect(received.update)
        worker.run()
        self.assertEqual(received, {"product_id": "M190737496RE"})
        fetch.assert_called_once_with(VALID_URL)

    @mock.patch("app.fetcher.fetch_metadata")
    def test_fetch_error_emits_message(self, fetch):
        fetch.side_effect = fetcher.FetchError("取得に失敗しました (HTTP 404)。")
        worker = FetchWorker(VALID_URL)
        messages: list[str] = []
        worker.failed.connect(messages.append)
        worker.run()
        self.assertEqual(messages, ["取得に失敗しました (HTTP 404)。"])

    def test_invalid_url_emits_message_without_network(self):
        worker = FetchWorker("https://example.com/lroc/view_lroc/DS/PR")
        messages: list[str] = []
        worker.failed.connect(messages.append)
        worker.run()
        self.assertEqual(len(messages), 1)
        self.assertIn("URL", messages[0])

    def test_signals_do_not_shadow_qthread_builtins(self):
        self.assertTrue(hasattr(FetchWorker, "succeeded"))
        self.assertTrue(hasattr(FetchWorker, "failed"))
        self.assertNotIn("finished_data", FetchWorker.__dict__)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: `ModuleNotFoundError: No module named 'app.workers'`

- [ ] **Step 3: Implement `app/workers.py`**

```python
"""UI から切り離したバックグラウンド処理。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app import fetcher


class FetchWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            data = fetcher.fetch_metadata(self._url)
        except ValueError as exc:
            self.failed.emit(str(exc))
        except fetcher.FetchError as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(data)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all tests PASS.

---

### Task 7: MainWindow

**Files:**
- Create: `app/main_window.py`
- Create: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `db.connect/upsert_product/list_products` (Task 3), `fetcher.parse_product_url` (Task 1), `workers.FetchWorker` (Task 6), `export_flow.*` (Task 5).
- Produces: `main_window.MainWindow(db_path, parent=None, settings=None)` with
  public widgets `url_edit`, `filter_edit`, `fetch_btn`, `table`, `detail_tree`,
  state `_visible: list[dict]` and `_fetch_worker`, and methods
  `_refresh_list(select=None)`, `_on_fetch()`, `_on_fetch_done(data)`,
  `_on_fetch_failed(message)`, `_current_record()`, `_selected_records()`,
  `_records_for_scope(scope)`, `_export()`, `_on_selection_changed()`, `_show_detail(record)`.

- [ ] **Step 1: Write the failing tests in `tests/test_main_window.py`**

```python
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
```

Note: `test_fetch_done_survives_db_error` patches `app.db.upsert_product`, so
`main_window` must call it as `db.upsert_product(...)` (module-qualified), which is how
the code below is written.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: `ModuleNotFoundError: No module named 'app.main_window'`

- [ ] **Step 3: Implement `app/main_window.py`**

```python
"""メインウィンドウ。"""

from __future__ import annotations

import json
import sqlite3

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHeaderView, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app import db, export_flow, fetcher
from app.workers import FetchWorker

LIST_COLUMNS = [
    "Product ID", "Original", "Orbit", "Center Lat", "Center Lon",
    "Resolution", "Pixel Width", "Pixel Height",
    "Incidence", "Emission", "Phase", "Slew",
]
LIST_KEYS = [
    "product_id", "original_product", "orbit_number", "center_latitude",
    "center_longitude", "resolution", "scaled_pixel_width", "scaled_pixel_height",
    "incidence_angle", "emission_angle", "phase_angle", "slew_angle",
]
DETAIL_GROUPS = [
    ("基本情報", ["Product", "Original product", "Pds dataset name",
                  "Target name", "Orbit number", "Start time", "Stop time"]),
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
        self._build_ui()
        self._build_menu()
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

        list_group = QGroupBox("登録一覧")
        list_layout = QVBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Product ID / Original / Orbit で絞り込み")
        self.filter_edit.textChanged.connect(lambda _text="": self._refresh_list())
        self.table = QTableWidget(0, len(LIST_COLUMNS))
        self.table.setHorizontalHeaderLabels(LIST_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.filter_edit)
        list_layout.addWidget(self.table)
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

    # --- 一覧 ---------------------------------------------------------------

    def _refresh_list(self, select: str | None = None) -> None:
        self._visible = db.list_products(self.conn, self.filter_edit.text())
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._visible))
        for row, record in enumerate(self._visible):
            for column, key in enumerate(LIST_KEYS):
                value = record.get(key)
                item = QTableWidgetItem("" if value is None else str(value))
                if value is None:
                    item.setForeground(QBrush(QColor(150, 150, 150)))
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        if select:
            for row, record in enumerate(self._visible):
                if record.get("product_id") == select:
                    self.table.selectRow(row)
                    break
        self._on_selection_changed()

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
                value = raw.get(label, "")
                text = str(value) if value not in (None, "") else "—"
                group.addChild(QTreeWidgetItem([label, text]))
                used.add(label)
            group.setExpanded(True)
        extra = {key: value for key, value in raw.items() if key not in used}
        if extra:
            group = QTreeWidgetItem(["その他（raw）", ""])
            self.detail_tree.addTopLevelItem(group)
            for key in sorted(extra):
                group.addChild(QTreeWidgetItem([key, str(extra[key])]))
        self.detail_tree.resizeColumnToContents(0)

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
        except (sqlite3.Error, ValueError) as exc:
            QMessageBox.warning(self, "保存エラー", str(exc))
            return
        product_id = data.get("product_id")
        self.url_edit.clear()
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
            self.conn.close()
        except sqlite3.Error:
            pass
        super().closeEvent(event)
```

Note on `_on_fetch_done`: it catches `sqlite3.Error` and `ValueError` only. The test
`test_fetch_done_survives_db_error` raises `RuntimeError`, so widen the handler to
`except Exception as exc:` in that method — the dialog wording stays the same. Widen it
like this:

```python
        try:
            db.upsert_product(self.conn, data)
        except Exception as exc:  # 保存失敗は UI を止めない
            QMessageBox.warning(self, "保存エラー", str(exc))
            return
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all `test_main_window` tests PASS and everything else still PASS.

- [ ] **Step 5: Re-run the whole suite**

Run: `py -m unittest discover -s tests -v`
Expected: `OK` — every test in every file passes.

### Task 8: Entry point, README, and verification

**Files:**
- Create: `main.py`
- Create: `README.md`
- Create: `docs/superpowers/specs/` is already present — no changes

**Interfaces:**
- Consumes: `main_window.MainWindow` (Task 7).
- Produces: a runnable `python main.py` entry point and a README describing setup,
  usage, and data location.

- [ ] **Step 1: Implement `main.py`**

```python
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
```

- [ ] **Step 2: Write `README.md`**

```markdown
# NAC QuickMap

LROC のプロダクト URL からメタデータを取得し、SQLite に溜めて
Excel に書き出すデスクトップツール。

## 必要環境

- Python 3.10 以上
- 依存パッケージ: `pip install -r requirements.txt`

## 起動

```powershell
python main.py
```

## 使い方

1. LROC のプロダクトページ URL を「自動取得」欄に貼り付け、
   `自動取得` を押す
2. 取得したメタデータが `lroc_data.db` に保存され、一覧と
   詳細（右ペイン）に表示される
3. `ファイル > Excelにエクスポート` で .xlsx を書き出す
   （範囲は「選択した行 / フィルタ結果 / すべて」から選択）

## データ

- 保存先: `lroc_data.db`（スクリプトと同じディレクトリ）
- 重複登録は `Product ID` をキーに上書きされる

## テスト

```powershell
py -m unittest discover -s tests -v
```
```

- [ ] **Step 3: Install the runtime dependencies**

Run: `py -m pip install -r requirements.txt`
Expected: installs `PyQt6`, `requests`, `beautifulsoup4`, `openpyxl`
without errors.

- [ ] **Step 4: Run the full test suite**

Run: `py -m unittest discover -s tests -v`
Expected: `OK` (all files, all tests).

- [ ] **Step 5: Smoke-test the entry point**

Run:
```powershell
py -c "import main; print('import ok')"
```
Expected: `import ok` (do not actually launch the GUI window in this step).

Then run the app manually to confirm the flow:
```powershell
py main.py
```
Paste a product URL (e.g.
`https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-3-CDR-V1.0/M190737496RC`),
verify the row appears, verify the detail tree shows values, then export a file and
open it. No automated assertion is required here.

- [ ] **Step 6: Check that no Qt import leaks into core modules**

Run:
```powershell
py -c "import app.fetcher, app.db, app.excel; print('core ok')"
```
Expected: `core ok` — these three modules must import without PyQt6.

---

## Self-Review Checklist

Run through these before declaring the plan done:

- [ ] No `TODO`, `TBD`, or `PLACEHOLDER` remains anywhere in this file.
- [ ] Every file mentioned in a Task's **Files** section is created or modified by
      exactly that Task.
- [ ] Every interface listed in an **Interfaces** section is actually defined in the
      Task's implementation step.
- [ ] Test files reference only functions/classes defined by an earlier Task or by
      the same Task.
- [ ] No `image_path` column exists in the created schema, no `Pillow` appears in
      `requirements.txt`, and no `scanner`/`image_view`/`ScanWorker` module is created.
      (Occurrences of those words as *negative assertions* in tests/constraints are fine.)
- [ ] `fetch_worker.finished` is never emitted or connected to — the signal is named
      `succeeded`/`failed` to avoid clashing with `QThread.finished`.
- [ ] `db.COLUMNS` has 13 fields (no `image_path`), matching `excel.KEYS` minus
      `created_at` (14). The list table has 12 columns, Excel has 14 headers,
      and `Resolution` is immediately followed by the two Scaled pixel columns
      in the list, in Excel, and in the spec.
- [ ] The last task's final verification step runs the complete suite.





