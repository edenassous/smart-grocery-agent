"""
פונקציית חיפוש מוצרים ב-DB האמיתי.
שלב חקר - לפני שמחברים ל-agent.
"""
import sqlite3
import sys
from rapidfuzz import process, fuzz
from pathlib import Path

DB_PATH = Path(__file__).parent / "real_prices.db"


def search_products(query: str, limit: int = 10) -> list[dict]:
    """משתמש ב-search_engine - מקור אחד לאמת."""
    from search_engine import search_products as _search
    results = _search(query, limit=limit)
    # התאמה לפורמט שה-display_results מצפה לו
    for r in results:
        r["prices"] = [
            {"chain": chain, "store": "—", "price": price}
            for chain, price in r["prices_per_chain"].items()
        ]
    return results


def display_results(query: str, results: list[dict]) -> None:
    """מציג את התוצאות בצורה ידידותית."""
    if not results:
        print(f"❌ לא נמצאו תוצאות עבור '{query}'")
        return

    print(f"\n🔍 תוצאות עבור '{query}' ({len(results)} מוצרים):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['item_name']} ({r['manufacturer']}) - התאמה: {r['match_score']}%")

        # מציג רק את המחיר הזול ביותר מכל רשת
        chains_min = {}
        for p in r["prices"]:
            chain = p["chain"]
            if chain not in chains_min or p["price"] < chains_min[chain]["price"]:
                chains_min[chain] = p

        for chain, p in sorted(chains_min.items(), key=lambda x: x[1]["price"]):
            print(f"   • {chain:12s}: {p['price']:>7.2f}₪  (סניף {p['store']})")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # כמה דוגמאות אם אין ארגומנט
        queries = ["חלב תנובה 3", "קוקה קולה", "לחם", "אבקת מרק עוף"]
    else:
        queries = [" ".join(sys.argv[1:])]

    for q in queries:
        results = search_products(q, limit=5)
        display_results(q, results)
        print("─" * 60)
