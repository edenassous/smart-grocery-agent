"""
Parser שמהפך XML של שקיפות מחירים ל-DB.
משתמש ב-ברקוד (ItemCode) כמזהה אוניברסלי בין רשתות.
"""
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass

DB_PATH = Path(__file__).parent / "real_prices.db"
DUMPS_PATH = Path(__file__).parent / "dumps"

# מיפוי שמות תיקיות → store_id קריא
CHAIN_FOLDERS = {
    "RamiLevy":  ("rami_levy", "רמי לוי"),
    "Shufersal": ("shufersal", "שופרסל"),
    "Victory":   ("victory",   "ויקטורי"),
}


@dataclass
class ParsedItem:
    chain_id: str
    store_id: str
    item_code: str       # ברקוד EAN
    item_name: str       # שם
    manufacturer: str
    price: float
    unit_qty: str
    quantity: float
    unit_of_measure: str
    is_weighted: bool


def init_real_db() -> None:
    """יוצר DB חדש (real_prices.db) לנתונים אמיתיים, לצד ה-mock הקיים."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        DROP TABLE IF EXISTS real_prices;
        DROP TABLE IF EXISTS real_products;
        DROP TABLE IF EXISTS real_stores;

        -- חנויות (רשתות)
        CREATE TABLE real_stores (
            chain_key TEXT PRIMARY KEY,         -- 'rami_levy', 'shufersal', ...
            chain_name TEXT NOT NULL,           -- 'רמי לוי'
            chain_id TEXT NOT NULL              -- '7290058140886'
        );

        -- מוצר אוניברסלי לפי ברקוד
        CREATE TABLE real_products (
            item_code TEXT PRIMARY KEY,         -- ברקוד EAN-13
            item_name TEXT NOT NULL,
            manufacturer TEXT,
            unit_qty TEXT,                      -- 'מיליליטר', 'גרם'
            quantity REAL,                      -- 750.00
            unit_of_measure TEXT,               -- '100 מיליליטר'
            is_weighted INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_real_products_name ON real_products(item_name);

        -- מחיר של מוצר ברשת מסוימת
        CREATE TABLE real_prices (
            chain_key TEXT NOT NULL REFERENCES real_stores(chain_key),
            item_code TEXT NOT NULL REFERENCES real_products(item_code),
            store_id TEXT NOT NULL,             -- 070, 089... (סניף ספציפי)
            price REAL NOT NULL,
            updated_at TEXT,
            PRIMARY KEY (chain_key, item_code, store_id)
        );
        CREATE INDEX idx_real_prices_item ON real_prices(item_code);
        CREATE INDEX idx_real_prices_chain ON real_prices(chain_key);
        """)

def parse_xml_file(xml_path: Path) -> tuple[str, str, list[ParsedItem]]:
    """
    מפרסר קובץ XML של מחירים. תומך ב-2 סכימות שונות:
      A) רמי לוי / שופרסל: <Root><Items><Item>...
      B) ויקטורי:          <Prices><Products><Product>...
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # זיהוי סכימה לפי שם ה-root
    if root.tag == "Prices":
        # סכימת ויקטורי
        items_container_name = "Products"
        item_tag = "Product"
        unit_measure_tag = "UnitMeasure"
        is_weighted_tag = "BisWeighted"
    else:
        # סכימת רמי לוי/שופרסל (root.tag == "Root")
        items_container_name = "Items"
        item_tag = "Item"
        unit_measure_tag = "UnitOfMeasure"
        is_weighted_tag = "bIsWeighted"

    chain_id = (root.findtext("ChainID") or "").strip()
    store_id = (root.findtext("StoreID") or "").strip()

    items: list[ParsedItem] = []
    items_root = root.find(items_container_name)
    if items_root is None:
        return chain_id, store_id, items

    for item_el in items_root.findall(item_tag):
        try:
            item_code = (item_el.findtext("ItemCode") or "").strip()
            item_name = (item_el.findtext("ItemName") or "").strip()
            price_str = (item_el.findtext("ItemPrice") or "0").strip()

            if not item_code or not item_name or not price_str:
                continue

            price = float(price_str)
            if price <= 0:
                continue

            quantity_str = (item_el.findtext("Quantity") or "0").strip()
            quantity = float(quantity_str) if quantity_str else 0.0

            items.append(ParsedItem(
                chain_id=chain_id,
                store_id=store_id,
                item_code=item_code,
                item_name=item_name,
                manufacturer=(item_el.findtext("ManufactureName") or "").strip(),
                price=price,
                unit_qty=(item_el.findtext("UnitQty") or "").strip(),
                quantity=quantity,
                unit_of_measure=(item_el.findtext(unit_measure_tag) or "").strip(),
                is_weighted=(item_el.findtext(is_weighted_tag) or "0").strip() == "1",
            ))
        except (ValueError, AttributeError):
            continue

    return chain_id, store_id, items
    


def load_all_dumps() -> dict[str, int]:
    """
    עובר על כל ה-dumps שהורדנו, פרסר ומכניס ל-DB.
    מחזיר: {chain_key: count} - כמה פריטים נטענו לכל רשת.
    """
    init_real_db()
    counts: dict[str, int] = {}

    with sqlite3.connect(DB_PATH) as conn:
        # להכניס את שלוש הרשתות
        for folder_name, (chain_key, chain_name) in CHAIN_FOLDERS.items():
            folder = DUMPS_PATH / folder_name
            if not folder.exists():
                print(f"⚠️  תיקייה לא קיימת: {folder}")
                continue

            xml_files = [f for f in folder.glob("*.xml") if f.name.startswith("Price")]
            if not xml_files:
                print(f"⚠️  אין קבצי Price ב-{folder}")
                continue

            chain_id_seen = None
            chain_count = 0

            for xml_file in xml_files:
                chain_id, store_id, items = parse_xml_file(xml_file)
                chain_id_seen = chain_id_seen or chain_id

                for item in items:
                    # upsert מוצר
                    conn.execute("""
                        INSERT OR IGNORE INTO real_products
                        (item_code, item_name, manufacturer, unit_qty,
                         quantity, unit_of_measure, is_weighted)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.item_code, item.item_name, item.manufacturer,
                        item.unit_qty, item.quantity, item.unit_of_measure,
                        1 if item.is_weighted else 0,
                    ))

                    # upsert מחיר
                    conn.execute("""
                        INSERT OR REPLACE INTO real_prices
                        (chain_key, item_code, store_id, price)
                        VALUES (?, ?, ?, ?)
                    """, (chain_key, item.item_code, store_id, item.price))

                    chain_count += 1

            # להוסיף את הרשת לטבלת stores (אם נמצאו פריטים)
            if chain_id_seen:
                conn.execute("""
                    INSERT OR REPLACE INTO real_stores
                    (chain_key, chain_name, chain_id) VALUES (?, ?, ?)
                """, (chain_key, chain_name, chain_id_seen))

            counts[chain_key] = chain_count
            print(f"  ✓ {chain_name}: נטענו {chain_count} שורות מחיר")

    return counts


def show_stats() -> None:
    """מציג סטטיסטיקה על מה שיש ב-DB."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        n_stores = conn.execute("SELECT COUNT(*) FROM real_stores").fetchone()[0]
        n_products = conn.execute("SELECT COUNT(*) FROM real_products").fetchone()[0]
        n_prices = conn.execute("SELECT COUNT(*) FROM real_prices").fetchone()[0]

        print(f"\n📊 סטטיסטיקה:")
        print(f"  חנויות: {n_stores}")
        print(f"  מוצרים ייחודיים: {n_products}")
        print(f"  שורות מחיר: {n_prices}")

        # מוצרים שיש להם מחיר ביותר מרשת אחת
        rows = conn.execute("""
            SELECT p.item_name, p.manufacturer,
                   COUNT(DISTINCT r.chain_key) AS n_chains,
                   GROUP_CONCAT(r.chain_key || ':' || r.price) AS prices
            FROM real_products p
            JOIN real_prices r ON r.item_code = p.item_code
            GROUP BY p.item_code
            HAVING n_chains >= 2
            ORDER BY n_chains DESC, p.item_name
            LIMIT 10
        """).fetchall()

        if rows:
            print(f"\n🔥 מוצרים שנמצאו במספר רשתות (טופ 10):")
            for r in rows:
                print(f"  • {r['item_name']} ({r['manufacturer']}) - {r['n_chains']} רשתות: {r['prices']}")
        else:
            print("\n  לא נמצאו מוצרים משותפים בין רשתות.")
            print("  זה כנראה כי הקבצים שהורדנו הם עדכונים חלקיים מסניפים שונים.")


if __name__ == "__main__":
    print("📦 טוען נתונים מ-dumps/...\n")
    counts = load_all_dumps()
    show_stats()
