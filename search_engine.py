"""
Search engine - מקור אחד לאמת. גם ה-CLI וגם ה-agent משתמשים בו.
"""
import sqlite3
from pathlib import Path
from rapidfuzz import process, fuzz

DB_PATH = Path(__file__).parent / "real_prices.db"

VARIATION_WORDS = {
    "חטיף", "חטיפי", "פריכיות", "פריכיית", "סוכריות", "סוכריית",
    "מארז", "מארזי", "מבצע", "כשלפ", "כשל\"פ",
    "תרסיס", "תרכיז", "אבקת",
    "לקפה", "מרוכז",
}


def search_products(query: str, limit: int = 10, min_score: int = 50) -> list[dict]:
    """
    חיפוש fuzzy + scoring חכם. מחזיר רשימת מוצרים עם המחירים בכל רשת.
    """
    query_words = [w for w in query.strip().split() if len(w) >= 2]
    if not query_words:
        return []

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # SQL prefilter: כל מילה חייבת להופיע
        where = " AND ".join(["item_name LIKE ?"] * len(query_words))
        params = [f"%{w}%" for w in query_words]
        candidates = conn.execute(f"""
            SELECT item_code, item_name, manufacturer
            FROM real_products
            WHERE {where}
            LIMIT 500
        """, params).fetchall()

        if not candidates:
            return []

        # scoring משולב
        scored = []
        for c in candidates:
            name = c["item_name"]
            base = fuzz.token_set_ratio(query, name)
            length_bonus = max(0, 30 - len(name)) * 0.5
            position_bonus = 10 if name.startswith(query_words[0]) else 0
            variation_penalty = sum(
                8 for vw in VARIATION_WORDS if vw in name and vw not in query
            )
            final = base + length_bonus + position_bonus - variation_penalty
            scored.append((c, final, base))

        scored.sort(key=lambda x: -x[1])
        top = scored[:limit]

        results = []
        for product, final_score, base_score in top:
            if base_score < min_score:
                continue
            prices = conn.execute("""
                SELECT chain_key, MIN(price) AS price
                FROM real_prices
                WHERE item_code = ?
                GROUP BY chain_key
                ORDER BY price
            """, (product["item_code"],)).fetchall()

            results.append({
                "item_code": product["item_code"],
                "item_name": product["item_name"],
                "manufacturer": product["manufacturer"] or None,
                "match_score": int(round(final_score)),
                "prices_per_chain": {r["chain_key"]: r["price"] for r in prices},
            })

        return results
