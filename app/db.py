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
    source_url TEXT,
    raw_metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

CREATE TABLE IF NOT EXISTS product_tags (
    product_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (product_id, tag_id),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""

COLUMNS: tuple[str, ...] = (
    "product_id", "original_product", "target_name", "orbit_number",
    "center_latitude", "center_longitude", "resolution",
    "scaled_pixel_width", "scaled_pixel_height",
    "incidence_angle", "emission_angle", "phase_angle", "slew_angle",
    "source_url",
)

_SELECT = (f"SELECT {', '.join('p.' + c for c in COLUMNS)}, p.raw_metadata_json, p.created_at"
           " FROM lroc_products p")

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
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _ensure_column(conn, "slew_angle", "REAL")
    _ensure_column(conn, "scaled_pixel_width", "REAL")
    _ensure_column(conn, "scaled_pixel_height", "REAL")
    _ensure_column(conn, "source_url", "TEXT")
    _ensure_column(conn, "color", "TEXT", table="tags")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, name: str, type_name: str,
                   table: str = "lroc_products") -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if name not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {type_name}")


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
        sql += (" WHERE p.product_id LIKE ? OR p.original_product LIKE ?"
                " OR CAST(p.orbit_number AS TEXT) LIKE ?")
        params = [like, like, like]
    sql += " ORDER BY p.id DESC"
    return [dict(record) for record in conn.execute(sql, params).fetchall()]


def get_now(conn: sqlite3.Connection) -> str:
    """SQLite 側の現在時刻 (UTC, 'YYYY-MM-DD HH:MM:SS')。created_at と同じ形式。"""
    return conn.execute("SELECT CURRENT_TIMESTAMP AS now").fetchone()["now"]


def list_products_since(conn: sqlite3.Connection, since_ts: str,
                        filter_text: str = "") -> list[dict[str, Any]]:
    """created_at が since_ts 以降の製品を返す。UPSERT で更新された行も含む。"""
    sql = _SELECT + " WHERE p.created_at >= ?"
    params: list[Any] = [since_ts]
    term = (filter_text or "").strip()
    if term:
        like = f"%{term}%"
        sql += (" AND (p.product_id LIKE ? OR p.original_product LIKE ?"
                " OR CAST(p.orbit_number AS TEXT) LIKE ?)")
        params.extend([like, like, like])
    sql += " ORDER BY p.created_at DESC, p.id DESC"
    return [dict(record) for record in conn.execute(sql, params).fetchall()]


def get_product(conn: sqlite3.Connection, product_id: str) -> dict[str, Any] | None:
    record = conn.execute(_SELECT + " WHERE p.product_id = ?", (product_id,)).fetchone()
    return dict(record) if record is not None else None


def list_tags(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    sql = """
        SELECT t.id, t.name, t.color, COUNT(pt.product_id) AS product_count
        FROM tags t
        LEFT JOIN product_tags pt ON pt.tag_id = t.id
        GROUP BY t.id, t.name, t.color
        ORDER BY t.name COLLATE NOCASE
    """
    return [dict(record) for record in conn.execute(sql).fetchall()]


TAG_PALETTE: tuple[str, ...] = (
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfa100", "#469990", "#9a6324", "#800000", "#808000",
)


def ensure_tag_colors(conn: sqlite3.Connection) -> None:
    """色が未設定のタグに、使われていないパレット色から順に割り当てる。"""
    rows = conn.execute("SELECT id, color FROM tags ORDER BY id").fetchall()
    used = {r["color"].lower() for r in rows if r["color"]}
    changed = False
    for r in rows:
        if r["color"]:
            continue
        free = [c for c in TAG_PALETTE if c not in used]
        color = free[0] if free else TAG_PALETTE[r["id"] % len(TAG_PALETTE)]
        conn.execute("UPDATE tags SET color = ? WHERE id = ?", (color, r["id"]))
        used.add(color)
        changed = True
    if changed:
        conn.commit()


def set_tag_color(conn: sqlite3.Connection, tag_name: str, color: str) -> None:
    conn.execute("UPDATE tags SET color = ? WHERE name = ?", (color, tag_name))
    conn.commit()


def list_product_tags_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """product_id -> タグ名リスト (名前順)。一覧のタグ表示・色付け用。"""
    sql = """
        SELECT pt.product_id, t.name
        FROM product_tags pt
        JOIN tags t ON t.id = pt.tag_id
        WHERE pt.product_id != ''
        ORDER BY t.name COLLATE NOCASE
    """
    result: dict[str, list[str]] = {}
    for row in conn.execute(sql):
        result.setdefault(row["product_id"], []).append(row["name"])
    return result


def get_product_tags(conn: sqlite3.Connection, product_id: str) -> list[str]:
    sql = """
        SELECT t.name
        FROM tags t
        JOIN product_tags pt ON pt.tag_id = t.id
        WHERE pt.product_id = ?
        ORDER BY t.name COLLATE NOCASE
    """
    return [row["name"] for row in conn.execute(sql, (product_id,)).fetchall()]


def set_product_tags(conn: sqlite3.Connection, product_id: str,
                     tag_names: list[str]) -> None:
    conn.execute("DELETE FROM product_tags WHERE product_id = ?", (product_id,))
    for name in tag_names:
        name = (name or "").strip()
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        conn.execute(
            "INSERT OR IGNORE INTO product_tags (product_id, tag_id) "
            "VALUES (?, (SELECT id FROM tags WHERE name = ?))",
            (product_id, name))
    conn.commit()


def add_tag_to_product(conn: sqlite3.Connection, product_id: str, tag_name: str) -> None:
    name = (tag_name or "").strip()
    if not name:
        return
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
    conn.execute(
        "INSERT OR IGNORE INTO product_tags (product_id, tag_id) "
        "VALUES (?, (SELECT id FROM tags WHERE name = ?))",
        (product_id, name))
    conn.commit()


def remove_tag_from_product(conn: sqlite3.Connection, product_id: str, tag_name: str) -> None:
    conn.execute(
        "DELETE FROM product_tags WHERE product_id = ? "
        "AND tag_id = (SELECT id FROM tags WHERE name = ?)",
        (product_id, tag_name))
    conn.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM product_tags)")
    conn.commit()


def delete_tag(conn: sqlite3.Connection, tag_name: str) -> None:
    conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
    conn.commit()


def rename_tag(conn: sqlite3.Connection, old_name: str, new_name: str) -> None:
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("タグ名を入力してください。")
    existing = conn.execute("SELECT id FROM tags WHERE name = ?", (new_name,)).fetchone()
    if existing and existing["id"] != _get_tag_id(conn, old_name):
        raise ValueError(f"タグ '{new_name}' は既に存在します。")
    conn.execute("UPDATE tags SET name = ? WHERE name = ?", (new_name, old_name))
    conn.commit()


def _get_tag_id(conn: sqlite3.Connection, tag_name: str) -> int | None:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    return row["id"] if row else None


def list_products_by_tag(conn: sqlite3.Connection, tag_name: str,
                         filter_text: str = "") -> list[dict[str, Any]]:
    return list_products_by_tags(conn, [tag_name], filter_text, match_all=True)


def list_products_by_tags(conn: sqlite3.Connection, tag_names: list[str],
                          filter_text: str = "",
                          match_all: bool = True) -> list[dict[str, Any]]:
    names = [n.strip() for n in (tag_names or []) if n and n.strip()]
    if not names:
        return list_products(conn, filter_text)
    sql = _SELECT
    params: list[Any] = []
    if match_all:
        placeholders = ", ".join("?" for _ in names)
        sql += f"""
            WHERE p.product_id IN (
                SELECT pt.product_id FROM product_tags pt
                JOIN tags t ON t.id = pt.tag_id
                WHERE t.name IN ({placeholders})
                GROUP BY pt.product_id
                HAVING COUNT(DISTINCT t.name) = ?
            )
        """
        params.extend(names)
        params.append(len(names))
    else:
        placeholders = ", ".join("?" for _ in names)
        sql += f"""
            WHERE p.product_id IN (
                SELECT pt.product_id FROM product_tags pt
                JOIN tags t ON t.id = pt.tag_id
                WHERE t.name IN ({placeholders})
            )
        """
        params.extend(names)
    term = (filter_text or "").strip()
    if term:
        like = f"%{term}%"
        sql += (" AND (p.product_id LIKE ? OR p.original_product LIKE ?"
                " OR CAST(p.orbit_number AS TEXT) LIKE ?)")
        params.extend([like, like, like])
    sql += " ORDER BY p.id DESC"
    return [dict(record) for record in conn.execute(sql, params).fetchall()]