"""
Tools layer - הפונקציות שה-agent יכול לקרוא, וה-schema שלהן.

עקרון מפתח: ה-LLM לא עושה חשבונות. הוא רק מתזמר.
- parse_shopping_list: משתמש ב-LLM עצמו (call פנימי) כי זו משימת NLU.
- search_product:      DB fuzzy search, דטרמיניסטי.
- get_delivery_info:   DB lookup, דטרמיניסטי.
- optimize_basket:     ILP, דטרמיניסטי לחלוטין.
"""
import json
from typing import Any
import anthropic

import db
from optimizer import optimize, BasketItem, PriceOption, StoreInfo


# -------------------- Tool schemas (לשליחה ל-Claude) --------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "parse_shopping_list",
        "description": (
            "מקבל טקסט חופשי בעברית עם רשימת קניות (למשל 'אני צריך 2 קילו עגבניות "
            "ו-5 פלפלים'), ומחזיר רשימה מובנית של פריטים עם כמויות ויחידת מידה."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_text": {"type": "string", "description": "הטקסט החופשי של המשתמש"}
            },
            "required": ["raw_text"],
        },
    },
    {
        "name": "search_product",
        "description": (
            "מחפש מוצר בכל החנויות באזור הנתון. מחזיר את כל אפשרויות המחיר "
            "(חנויות, מחיר ליחידה). השתמש בשם הכי פשוט ונפוץ ('עגבניה' ולא 'עגבנייה שרי'). "
            "יש לקרוא לכלי הזה פעם אחת לכל מוצר ברשימה."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "region": {
                    "type": "string",
                    "enum": ["tel_aviv", "haifa", "jerusalem", "beer_sheva"],
                },
            },
            "required": ["product_name", "region"],
        },
    },
    {
        "name": "get_delivery_info",
        "description": (
            "מחזיר דמי משלוח וסף הזמנה מינימלי לחנות באזור. "
            "קרא רק לחנויות שמופיעות בתוצאות search_product."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string"},
                "region": {
                    "type": "string",
                    "enum": ["tel_aviv", "haifa", "jerusalem", "beer_sheva"],
                },
            },
            "required": ["store_id", "region"],
        },
    },
    {
        "name": "optimize_basket",
        "description": (
            "מחשב את חלוקת הסל האופטימלית בין חנויות (ILP). "
            "קרא אחרי שאספת את כל המחירים ומידע המשלוחים. "
            "מחזיר סלים מפוצלים עם עלות כוללת."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "basket": {
                    "type": "array",
                    "description": "פריטי הסל הרצוי",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string", "enum": ["kg", "unit"]},
                        },
                        "required": ["product_name", "quantity", "unit"],
                    },
                },
                "prices": {
                    "type": "object",
                    "description": (
                        "מילון: product_name -> [{store_id, price_per_unit}, ...]. "
                        "בנה את זה מתוצאות search_product."
                    ),
                },
                "stores": {
                    "type": "object",
                    "description": (
                        "מילון: store_id -> {store_name, delivery_fee, min_order}. "
                        "בנה מתוצאות get_delivery_info."
                    ),
                },
            },
            "required": ["basket", "prices", "stores"],
        },
    },
]


# -------------------- Tool implementations --------------------

_llm = anthropic.Anthropic()  # משותף לכל הקריאות הפנימיות


def _tool_parse_shopping_list(raw_text: str) -> dict[str, Any]:
    """משתמש ב-Haiku (זול) לפרסור. מחזיר JSON מובנה."""
    resp = _llm.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=(
            "אתה מפרסר רשימות קניות בעברית. החזר JSON בפורמט הבא בלבד, בלי הסברים:\n"
            '{"items":[{"product_name":"...","quantity":<num>,"unit":"kg"|"unit"}]}\n'
            "השתמש בשם בסיסי ונפוץ (עגבניה, מלפפון, פלפל אדום). "
            "ברירת מחדל ל-quantity: אם המשתמש אמר 'קילו' -> kg, אם 'יחידה'/'חבילה' -> unit. "
            "אם לא ציין כמות, quantity=1."
        ),
        messages=[{"role": "user", "content": raw_text}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    # להוריד אפשר code fences אם הגיעו
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1].rsplit("\n", 1)[0]
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


def _tool_search_product(product_name: str, region: str) -> dict[str, Any]:
    results = db.search_product(product_name, region)
    return {"query": product_name, "region": region, "results": results}


def _tool_get_delivery_info(store_id: str, region: str) -> dict[str, Any]:
    rule = db.get_delivery_rule(store_id, region)
    if not rule:
        return {"error": f"אין כלל משלוח לחנות {store_id} באזור {region}"}
    return {"store_id": store_id, "region": region, **rule}


def _tool_optimize_basket(basket: list, prices: dict, stores: dict) -> dict[str, Any]:
    basket_items = [BasketItem(**item) for item in basket]
    prices_parsed = {
        name: [PriceOption(**opt) for opt in opts]
        for name, opts in prices.items()
    }
    stores_parsed = {
        sid: StoreInfo(
            store_id=sid,
            store_name=info.get("store_name", sid),
            delivery_fee=info["delivery_fee"],
            min_order=info["min_order"],
        )
        for sid, info in stores.items()
    }
    result = optimize(basket_items, prices_parsed, stores_parsed)
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
    "get_delivery_info":   lambda args: _tool_get_delivery_info(**args),
    "optimize_basket":     lambda args: _tool_optimize_basket(**args),
}


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    if name not in DISPATCH:
        return {"error": f"unknown tool: {name}"}
    try:
        return DISPATCH[name](args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
