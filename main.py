"""
CLI entry point.

שימוש:
  python main.py init
  python main.py run "2 קילו עגבניות, 1 קילו מלפפונים, 5 פלפלים אדומים"
  python main.py run "..." --region haifa
  python main.py test-optimizer   # בודק שה-ILP עובד בלי LLM
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import argparse

import db
import mock_data
from agent import run_agent


def cmd_init() -> None:
    db.init_schema()
    mock_data.load_mock_data()
    print("✓ DB מוכן")


def cmd_run(message: str, region: str) -> None:
    print(f"🛒 בקשה: {message}")
    print(f"📍 אזור: {region}")
    print("─" * 60)
    answer = run_agent(message, region, verbose=True)
    print("─" * 60)
    print(answer)


def cmd_test_optimizer() -> None:
    """בודק את ה-optimizer ישירות, בלי LLM. סל גדול שדורש פיצול."""
    from optimizer import optimize, BasketItem, PriceOption, StoreInfo

    # סל גדול שמציג פיצול אמיתי
    basket = [
        BasketItem("עגבניה",     10.0, "kg"),
        BasketItem("מלפפון",     5.0,  "kg"),
        BasketItem("פלפל אדום",  3.0,  "kg"),
        BasketItem("פלפל צהוב",  2.0,  "kg"),
        BasketItem("בצל",        5.0,  "kg"),
        BasketItem("תפוח אדמה",  8.0,  "kg"),
        BasketItem("חסה",        3.0,  "unit"),
        BasketItem("ברוקולי",    2.0,  "kg"),
    ]
    # A זולה מאוד באבן-דרך, משלוח יקר.
    # B יקרה מאוד, משלוח חינם + סף נמוך.
    prices = {
        "עגבניה":     [PriceOption("A", 4.90), PriceOption("B", 9.50)],   # A הרבה יותר זול
        "מלפפון":     [PriceOption("A", 4.50), PriceOption("B", 8.50)],   # A הרבה יותר זול
        "פלפל אדום":  [PriceOption("A", 11.90),PriceOption("B", 18.50)],
        "פלפל צהוב":  [PriceOption("A", 25.00),PriceOption("B", 14.50)],  # B יותר זול!
        "בצל":        [PriceOption("A", 3.90), PriceOption("B", 7.50)],
        "תפוח אדמה":  [PriceOption("A", 3.00), PriceOption("B", 6.90)],
        "חסה":        [PriceOption("A", 9.90), PriceOption("B", 4.50)],   # B יותר זול!
        "ברוקולי":    [PriceOption("A", 18.00),PriceOption("B", 10.90)],  # B יותר זול!
    }
    stores = {
        "A": StoreInfo("A", "חנות A (ירקנייה בשוק)",   29.90, 100),
        "B": StoreInfo("B", "חנות B (סופרמרקט)",        0.00,  80),   # משלוח חינם מעל 80₪
    }

    res = optimize(basket, prices, stores)
    if not res.feasible:
        print(f"❌ לא נמצא פתרון: {res.infeasibility_reason}")
        return

    print(f"💰 סה״כ: {res.total_cost}₪ (מוצרים {res.items_cost} + משלוח {res.delivery_cost})")
    print(f"📦 מספר סלים: {len(res.baskets)}")
    for store_id, items in res.baskets.items():
        store_name = stores[store_id].store_name
        fee = stores[store_id].delivery_fee
        print(f"\n  [{store_id}] {store_name} - סכום מוצרים: {res.store_totals[store_id]}₪, משלוח: {fee}₪")
        for it in items:
            print(f"    • {it['quantity']} {it['unit']} {it['product']} @ {it['unit_price']}₪ = {it['line_total']}₪")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="יוצר DB וטוען mock data")
    sub.add_parser("test-optimizer", help="בודק את ה-ILP ישירות")

    run = sub.add_parser("run", help="מריץ את ה-agent")
    run.add_argument("message", help="בקשת המשתמש")
    run.add_argument(
        "--region",
        default="tel_aviv",
        choices=["tel_aviv", "haifa", "jerusalem", "beer_sheva"],
    )

    args = p.parse_args()
    if args.cmd == "init":
        cmd_init()
    elif args.cmd == "test-optimizer":
        cmd_test_optimizer()
    elif args.cmd == "run":
        cmd_run(args.message, args.region)


if __name__ == "__main__":
    main()
