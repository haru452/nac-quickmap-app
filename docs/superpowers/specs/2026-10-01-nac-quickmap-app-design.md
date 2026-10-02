# NAC QuickMap App — Design Spec

**Date:** 2026-10-01
**Target path:** `C:\Users\haru0\club\class\nac-quickmap-app`
**Status:** Approved (design, rev.3 — Scaled pixel width/height added to list + Excel), pending implementation plan

---

## 1. Purpose

A desktop tool that turns LROC product page URLs into a growing local table of
metadata — especially the slew / emission / incidence angles — and exports that table
to a named Excel workbook.

The whole loop is: **paste URL → fetch that page's metadata → row appears in the table →
repeat → export to Excel.** Nothing else. The app performs no filesystem scanning and
displays no images.

Image file names are deliberately *not* a data source: the downloaded image of an
observation is named after the product (`M1131778978LC_pyr.tif` ≈ product
`M1131778978L`), so the `Product ID` / `Original Product` columns already carry the
image's name. The user matches files to rows by eye.

## 2. Constraints & Stack

| Item | Value |
| :--- | :--- |
| Language | Python 3.10+ (verified runtime: 3.13.15) |
| GUI | PyQt6 (installed: 6.11.0) |
| Database | `sqlite3`, file `lroc_data.db` |
| HTTP / parsing | `requests`, `beautifulsoup4` |
| Excel export | `openpyxl` |
| Tests | `unittest` (stdlib), run with `python -m unittest discover -s tests -v` |

No image-decoding library is required (no preview), and `Pillow` is not a dependency.

Source of truth for metadata: the LROC archive product page, e.g.
`https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-3-CDR-V1.0/M190737496RC`
(alias host `wms.lroc.im-ldi.com` redirects POSTs; GET works on both).

### Verified facts this design relies on

- The product page contains **exactly one** `<table>` with 65 `<tr>` rows.
- Row 1 has `colspan="2"` and holds download links (EDR `.IMG`, CDR `.IMG`, browse PTIF).
  It must be skipped by the parser.
- Every other row is `<tr><td>Label</td><td>Value</td></tr>` (the closing tags are
  occasionally mismatched — `<td>…</th>` — so parsing must use a tolerant HTML parser).
- The page exposes `Product`, `Original product`, `Target name`, `Orbit number`,
  `Slew angle`, `Resolution`, `Emission angle`, `Incidence angle`, `Phase angle`,
  `Center latitude`, `Center longitude`, `Scaled pixel width`, `Scaled pixel height`,
  plus corner coordinates, timestamps, and instrument housekeeping.
- Verified values for `M190737496RC`: `Scaled pixel width = 1.1`,
  `Scaled pixel height = 0.78`. Some calibration products leave these (and other
  numerics) blank — blank means `NULL`, never `0`.
- `Product` is `M190737496RE` for **both** the EDR and CDR URL of the same observation,
  so it is a stable uniqueness key.
- The archive's *Image Search* POST endpoint returns HTTP 500 and is therefore **not**
  used anywhere in this app. Lookup is URL-driven only.

## 3. Feature Specification

### 3.1 Input — link only

One input method: paste a product URL, press 「自動取得」. Repeat as many times as needed
to build the table.

Accepted URL shape:

```
https://<host>/lroc/view_lroc/<dataset>/<product>
  e.g. LRO-L-LROC-3-CDR-V1.0 / M190737496RC
```

- `<host>` may be `data.lroc.im-ldi.com` or `wms.lroc.im-ldi.com`; scheme may be http or
  https. Anything else → warning dialog, no network call.
- Re-submitting a URL for a product already in the DB **overwrites** that row
  (`INSERT ... ON CONFLICT(product_id) DO UPDATE`) rather than creating a duplicate.
- Free-text / key-value paste input from the original requirements is **out of scope**
  by explicit user decision.

### 3.2 Browsing & search

- Left list is a `QTableWidget` with columns:
  `Product ID | Original | Orbit | Center Lat | Center Lon | Resolution | Pixel Width |
   Pixel Height | Incidence | Emission | Phase | Slew`
- A `QLineEdit` filter narrows the list by **Product ID, Original product, or Orbit
  number**, case-insensitive substring match.
- The list uses `QAbstractItemView.ExtendedSelection`: the user can Ctrl/Shift-click to
  select several rows, so that images of one area can be gathered into a single named
  workbook (see 3.3).
- Selecting rows shows the detail tree on the right; when several rows are selected the
  right pane shows the **first** of them.

### 3.3 Excel export

Menu: ファイル →「Excelにエクスポート」.

**Scope dialog** (`QMessageBox`, shown only when it is ambiguous):

| Scope | Exports | Shown when |
| :--- | :--- | :--- |
| 選択した行 | the multi-selected rows | one or more rows are selected |
| フィルタ結果 | every row currently passing the filter | filter box is non-empty |
| すべて | every row in the database | always offered as the fallback |

If exactly one scope is applicable the dialog is skipped and that scope is used.

**Save dialog** (`QFileDialog.getSaveFileName`) then asks for the destination. The
suggested default name is `lroc_export_YYYYMMDD_HHMMSS.xlsx`; the last used directory is
restored via `QSettings`. `.xlsx` is appended automatically if the user omits it.
Choosing an existing file asks for overwrite confirmation. This lets the user name each
workbook after the area it covers (e.g. `sinus_iridum.xlsx`).

Sheet columns, one row per exported record:

| Column | Source |
| :--- | :--- |
| Product ID | `product_id` — this is also the image's file-name stem |
| Original Product | `original_product` |
| Target | `target_name` |
| Orbit | `orbit_number` |
| Center Latitude | `center_latitude` |
| Center Longitude | `center_longitude` |
| Resolution | `resolution` |
| Scaled Pixel Width | `scaled_pixel_width` |
| Scaled Pixel Height | `scaled_pixel_height` |
| Slew Angle | `slew_angle` |
| Incidence Angle | `incidence_angle` |
| Emission Angle | `emission_angle` |
| Phase Angle | `phase_angle` |
| Registered At | `created_at` |

Numeric cells are written as numbers (not text) so Excel can sort and compute on them.
Missing values (`NULL`) become blank cells. A bold header row and a frozen first row
are applied.

## 4. Data Model

File: `lroc_data.db`, table `lroc_products`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INTEGER PK AUTOINCREMENT | |
| `product_id` | TEXT UNIQUE | page `Product`, e.g. `M190737496RE` |
| `original_product` | TEXT | e.g. `nacr00098809` |
| `target_name` | TEXT | e.g. `MOON` |
| `orbit_number` | INTEGER | |
| `center_latitude` | REAL | |
| `center_longitude` | REAL | |
| `resolution` | REAL | m/px |
| `scaled_pixel_width` | REAL | page `Scaled pixel width` |
| `scaled_pixel_height` | REAL | page `Scaled pixel height` |
| `incidence_angle` | REAL | |
| `emission_angle` | REAL | |
| `phase_angle` | REAL | |
| `slew_angle` | REAL | added beyond the original requirement list |
| `raw_metadata_json` | TEXT | every parsed key/value, JSON object |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | |

There is **no** `image_path` column: nothing on disk is referenced.

- Keys not mapped to a column (timestamps, corner coordinates, temperatures, …) are kept
  only in `raw_metadata_json`.
- Missing numeric values on the page (they are blank for some calibration products) are
  stored as `NULL`, never as `0`.
- `upsert_product` uses `INSERT ... ON CONFLICT(product_id) DO UPDATE`, which sets
  `created_at = CURRENT_TIMESTAMP`. The export header therefore labels it `Registered At`
  meaning "last registered". `id` stays stable across re-fetches.
- Schema creation is idempotent (`CREATE TABLE IF NOT EXISTS`). Columns added after a
  DB's creation (`slew_angle`, `scaled_pixel_width`, `scaled_pixel_height`) are handled
  with a guarded `ALTER TABLE` at startup.

## 5. Component Design

```
main.py
  └─ QApplication → MainWindow

app/fetcher.py    parse_product_url(url) -> (dataset, product) | ValueError
                  fetch_metadata(url)    -> dict          # network + parse
                  split_rows(html)       -> list[(k, v)]  # pure, unit-testable
                  map_columns(kv: dict)  -> dict          # pure, unit-testable

app/db.py         connect(path), init_schema(conn)
                  upsert_product(conn, row), list_products(conn, filter_text),
                  get_product(conn, pid)

app/workers.py    FetchWorker(QThread): url -> signals succeeded(dict) / failed(str)

app/excel.py      export_xlsx(rows, path) -> None

app/main_window.py MainWindow(QMainWindow): layout, wiring, dialogs
```

There is no `scanner.py` and no `image_view.py`.

Dependency direction is one-way: `main_window` → `workers` → `fetcher` → `db`.
`fetcher`, `db`, and `excel` contain no Qt imports, so they are testable headlessly.

### Threading contract

- Every network call runs inside a `QThread` subclass.
- Workers emit only signals; they never touch widgets. The signal is named `succeeded`,
  not `finished`, to avoid colliding with `QThread.finished`.
- While a worker runs, the 自動取得 button is disabled and a status-bar message shows
  progress. On `failed`, the button is re-enabled and a `QMessageBox.warning` explains
  the cause in plain language (timeouts, HTTP status, and parse failures get distinct
  messages).
- The worker is kept as a `MainWindow` attribute so it is not garbage-collected while
  running. A second fetch cannot start until the first finishes (button disabled).

### Error handling matrix

| Condition | Behaviour |
| :--- | :--- |
| Empty URL | warning dialog, no request issued |
| URL does not match the expected shape / wrong host | warning dialog, no request issued |
| DNS / connection failure | warning: 通信エラー, include host |
| Timeout | warning: タイムアウト |
| HTTP 404 / 5xx | warning: include status code |
| Page fetched but no metadata table | warning: ページ解析に失敗 |
| Product missing numeric fields | store NULL, show `—` in the UI |
| Product missing `Product` label | warning: Product が見つかりません |
| SQLite write failure | warning: 保存エラー, include SQLite message |
| Export path not writable | warning |
| Export target exists | ask for overwrite confirmation before writing |
| Export scope empty (filter matches nothing) | warning: 対象がありません |

## 6. UI Layout

`QSplitter` (horizontal), window title `NAC QuickMap`.

**Left pane (`QVBoxLayout`, two `QGroupBox`)**

1. **自動取得** — `QLineEdit` (URL) + 「自動取得」`QPushButton`
2. **登録一覧** — filter `QLineEdit` + `QTableWidget`
   - selection mode: `ExtendedSelection` (Ctrl/Shift multi-select)
   - any selection change refreshes the right pane with the first selected row

**Right pane (`QVBoxLayout`)** — one widget:

1. **メタデータ詳細** — `QTreeWidget`, two columns (`項目` / `値`), four groups:
   - 基本情報: Product, Original product, Pds dataset name, Target name, Orbit,
     Start time, Stop time
   - 観測ジオメトリ: Center latitude, Center longitude, Resolution, Incidence angle,
     Emission angle, Phase angle, Slew angle, Spacecraft altitude
   - 画像・その他: Image lines, Line samples, Sample bits, Product version, Data quality
   - その他（raw）: every remaining key from `raw_metadata_json`
   - absent values render as `—`

Menu bar: `ファイル` → `Excelにエクスポート`, `終了`.

## 7. Deliverables

```
nac-quickmap-app/
  main.py
  app/{__init__,db,fetcher,workers,excel,main_window}.py
  tests/{test_fetcher,test_db,test_excel,test_workers,test_main_window}.py
  tests/fixtures/product_page.html
  requirements.txt
  README.md            # install, launch, usage
  docs/superpowers/specs/2026-10-01-nac-quickmap-app-design.md
```

`lroc_data.db` is created at runtime and is not a source file.

## 8. Acceptance criteria

1. `python main.py` opens the window with no console errors.
2. Pasting the `M190737496RC` URL and pressing 自動取得 creates a row whose
   `slew_angle ≈ 0.0127`, `incidence_angle = 45.78`, `emission_angle = 1.18`,
   `center_latitude = -0.3`, `center_longitude = 339.1`, `orbit_number = 13151`,
   `scaled_pixel_width = 1.1`, `scaled_pixel_height = 0.78`.
3. Repeating step 2 for the same URL leaves exactly one row for that product.
4. Fetching several different URLs builds up the table with one row each.
5. Selecting a row fills the detail tree with its four groups; blank page values show `—`.
6. Typing a partial Product ID in the filter box narrows the list.
7. Export produces an `.xlsx` whose numeric angle columns open as numbers in Excel.
8. Selecting several rows and exporting **選択した行** writes exactly those rows to the
   user-chosen file name (e.g. `sinus_iridum.xlsx`) in the chosen folder.
9. Exporting twice to the same path asks for overwrite confirmation before replacing it.
10. Disabling the network (invalid host) shows a warning dialog and leaves the UI usable.
11. `python -m unittest discover -s tests -v` passes.

## 9. Out of scope

- Any filesystem scanning, image preview, or image downloading.
- Referencing local files at all (no `image_path`).
- Text/key-value paste input.
- The archive's search endpoint (HTTP 500).
- Editing metadata values by hand inside the app.
