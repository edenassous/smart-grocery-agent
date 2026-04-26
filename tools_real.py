"""
Tools layer לסוכן, מבוססי DB אמיתי (real_prices.db).
מבוסס על tools.py הישן אבל עובד מול הנתונים האמיתיים.
"""
import json
import sqlite3
from pathlib import Path
from typing import Any

import anthropic
from rapidfuzz import process, fuzz

from optimizer import optimize, BasketItem, PriceOption, StoreInfo

DB_PATH = Path(__file__).parent / "real_prices.db"

# דמי משלוח קבועים זמנית. בפרודקשן זה יבוא מ-scraper נפרד או טבלה ב-DB.
DEFAULT_DELIVERY = {
    "rami_levy": {"chain_name": "רמי לוי", "delivery_fee": 24.90, "min_order": 150.0},
    "shufersal": {"chain_name": "שופרסל",  "delivery_fee": 29.90, "min_order": 150.0},
    "victory":   {"chain_name": "ויקטורי", "delivery_fee": 19.90, "min_order": 150.0},
}

# -------------------- Tool schemas (לשליחה ל-Claude) --------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "parse_shopping_list",
        "description": (
            "מקבל טקסט חופשי בעברית עם רשימת קניות ומחזיר רשימה מובנית של פריטים. "
            "החזר רק את שמות המוצרים בכלליות (למשל 'חלב 3%', 'במבה', 'קוקה קולה') בלי מותגים."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_text": {"type": "string"}
            },
            "required": ["raw_text"],
        },
    },
    {
        "name": "search_product",
        "description": (
            "מחפש מוצר במאגר המחירים האמיתי של 3 הרשתות. "
            "מחזיר רשימה של עד 5 מוצרים תואמים, כל אחד עם המחיר שלו בכל רשת. "
            "השם יכול להיות חלקי - 'חלב 3' יחזיר חלב 3%."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "max_results": {
                    "type": "integer",
                    "description": "מקסימום תוצאות (ברירת מחדל 5)",
                },
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "optimize_basket",
        "description": (
            "מחשב פיצול אופטימלי של סל בין רשתות, כולל דמי משלוח וסף הזמנה. "
            "קוראים לזה אחרי שמצאת את כל המוצרים. "
            "מקבל לכל פריט את הברקוד שבחרת ואת הכמות. "
            "אם feasible=false, סביר שהסל קטן מדי לסף הזמנה."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_code": {"type": "string", "description": "ברקוד המוצר"},
                            "item_name": {"type": "string", "description": "שם להצגה"},
                            "quantity": {"type": "number"},
                        },
                        "required": ["item_code", "item_name", "quantity"],
                    },
                },
            },
            "required": ["items"],
        },
    },
]


# -------------------- Tool implementations --------------------

_llm = anthropic.Anthropic()


def _tool_parse_shopping_list(raw_text: str) -> dict[str, Any]:
    """משתמש ב-Haiku (זול) לפרסור."""
    resp = _llm.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=(
            "אתה מפרסר רשימות קניות בעברית. החזר JSON בפורמט:\n"
            '{"items":[{"product_name":"...","quantity":<num>}]}\n'
            "השתמש בשם כללי (חלב 3%, במבה, קוקה קולה). "
            "אם לא ציין כמות, quantity=1. החזר JSON בלבד."
        ),
        messages=[{"role": "user", "content": raw_text}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1].rsplit("\n", 1)[0]
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


def _tool_search_product(product_name: str, max_results: int = 5) -> dict[str, Any]:
    """משתמש ב-search_engine - מקור אחד לאמת."""
    from search_engine import search_products
    results = search_products(product_name, limit=max_results)
    return {"query": product_name, "results": results}


def _tool_optimize_basket(items: list[dict]) -> dict[str, Any]:
    """
    מקבל [{item_code, item_name, quantity}, ...] ובונה את ה-input ל-optimizer.
    שולף מחירים מ-DB אמיתי, משלב עם דמי משלוח קבועים.
    """
    basket_items = []
    prices: dict[str, list[PriceOption]] = {}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for it in items:
            item_code = it["item_code"]
            item_name = it["item_name"]
            quantity = float(it["quantity"])

            # מצא את כל המחירים של המוצר הזה
            rows = conn.execute("""
                SELECT chain_key, MIN(price) AS price
                FROM real_prices
                WHERE item_code = ?
                GROUP BY chain_key
            """, (item_code,)).fetchall()

            if not rows:
                continue  # מוצר לא קיים - יסומן כ-unfulfilled

            basket_items.append(BasketItem(
                product_name=item_name, quantity=quantity, unit="unit"
            ))
            prices[item_name] = [
                PriceOption(store_id=r["chain_key"], price_per_unit=r["price"])
                for r in rows
            ]

    stores = {
        chain_key: StoreInfo(
            store_id=chain_key,
            store_name=info["chain_name"],
            delivery_fee=info["delivery_fee"],
            min_order=info["min_order"],
        )
        for chain_key, info in DEFAULT_DELIVERY.items()
    }

    result = optimize(basket_items, prices, stores)
    return {
        "feasible": result.feasible,
        "infeasibility_reason": result.infeasibility_reason,
        "total_cost": result.total_cost,
        "items_cost": result.items_cost,
        "delivery_cost": result.delivery_cost,
        "baskets": result.baskets,
        "store_totals": result.store_totals,
        "unfulfilled": result.unfulfilled,
    }


# -------------------- Dispatcher --------------------

DISPATCH = {
    "parse_shopping_list": lambda args: _tool_parse_shopping_list(**args),
    "search_product":      lambda args: _tool_search_product(**args),
    "optimize_basket":     lambda args: _tool_optimize_basket(**args),
}


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    if name not in DISPATCH:
        return {"error": f"unknown tool: {name}"}
    try:
        return DISPATCH[name](args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
