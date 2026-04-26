"""
SQLite layer. מחזיק:
  stores         - חנויות (שם, אזורים)
  products       - מוצרים שזיהינו (שם מנורמל + יחידת מידה)
  prices         - מחיר למוצר בחנות מסויימת (כולל זמינות)
  delivery_rules - דמי משלוח + סף הזמנה לפי חנות+אזור

לחיפוש "מלפפון" נגד "מלפפון ירוק מחווה X" משתמשים ב-rapidfuzz.
בפרודקשן כדאי PostgreSQL + pg_trgm או embeddings לחיפוש סמנטי.
"""
import sqlite3
from pathlib import Path
from rapidfuzz import process, fuzz
from typing import Any

DB_PATH = Path(__file__).parent / "veggies.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema() -> None:
    with get_conn() as conn:
        conn.executescript("""
        DROP TABLE IF EXISTS prices;
        DROP TABLE IF EXISTS delivery_rules;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS stores;

        CREATE TABLE stores (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            regions      TEXT NOT NULL  -- csv of supported regions
        );

        CREATE TABLE products (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical    TEXT NOT NULL,   -- "עגבניה"
            unit         TEXT NOT NULL    -- 'kg' | 'unit'
        );
        CREATE INDEX idx_products_canonical ON products(canonical);

        CREATE TABLE prices (
            store_id     TEXT NOT NULL REFERENCES stores(id),
            product_id   INTEGER NOT NULL REFERENCES products(id),
            price        REAL NOT NULL,    -- ₪ per unit (kg or item)
            available    INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (store_id, product_id)
        );

        CREATE TABLE delivery_rules (
            store_id     TEXT NOT NULL REFERENCES stores(id),
            region       TEXT NOT NULL,
            fee          REAL NOT NULL,    -- ₪
            min_order    REAL NOT NULL,    -- ₪ - סף הזמנה מינימום
            PRIMARY KEY (store_id, region)
        );
        """)


# ---------- queries ----------

def list_stores(region: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, regions FROM stores"
        ).fetchall()
    return [dict(r) for r in rows if region in r["regions"].split(",")]


def search_product(query: str, region: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    מחפש מוצר בטקסט חופשי ("עגבנייה", "מלפפון מחווה").
    מחזיר לכל התאמה fuzzy את כל המחירים מכל החנויות הרלוונטיות לאזור.
    """
    with get_conn() as conn:
        products = conn.execute("SELECT id, canonical, unit FROM products").fetchall()
        if not products:
            return []

        # fuzzy match על השם הקנוני
        names = [p["canonical"] for p in products]
        matches = process.extract(query, names, scorer=fuzz.WRatio, limit=limit)
        # matches = [(name, score, index), ...]
        matched_ids = [products[idx]["id"] for _, score, idx in matches if score >= 60]

        if not matched_ids:
            return []

        placeholders = ",".join("?" * len(matched_ids))
        rows = conn.execute(f"""
            SELECT p.product_id, pr.canonical, pr.unit,
                   p.store_id, s.name AS store_name, p.price, p.available,
                   s.regions
            FROM prices p
            JOIN products pr ON pr.id = p.product_id
            JOIN stores   s  ON s.id  = p.store_id
            WHERE p.product_id IN ({placeholders})
              AND p.available = 1
            ORDER BY pr.canonical, p.price
        """, matched_ids).fetchall()

    return [
        {
            "product_id": r["product_id"],
            "product_name": r["canonical"],
            "unit": r["unit"],
            "store_id": r["store_id"],
            "store_name": r["store_name"],
            "price": r["price"],
        }
        for r in rows
        if region in r["regions"].split(",")
    ]


def get_delivery_rule(store_id: str, region: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT fee, min_order FROM delivery_rules WHERE store_id=? AND region=?",
            (store_id, region),
        ).fetchone()
    return dict(row) if row else None
