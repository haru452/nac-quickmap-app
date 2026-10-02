"""LROC 製品ページの取得と解析。Qt には依存しない。"""

from __future__ import annotations

import re
from typing import Any

import requests
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
    "Source URL": "source_url",
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
    soup = BeautifulSoup((html or "").replace("</th>", "</td>"), "html.parser")
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


TEXT_FIELDS = frozenset({"product_id", "original_product", "target_name", "source_url"})
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
