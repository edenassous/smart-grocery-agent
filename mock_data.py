"""
Mock data. 4 חנויות * 20 מוצרים עם מחירים אקראיים-אך-ריאליסטיים.
מחליפים את זה ב-scraper.py אמיתי.
"""
import random
from db import get_conn

random.seed(42)  # deterministic

STORES = [
    {"id": "rami_levy",  "name": "רמי לוי",        "regions": "tel_aviv,haifa,jerusalem"},
    {"id": "shufersal",  "name": "שופרסל",         "regions": "tel_aviv,haifa,jerusalem,beer_sheva"},
    {"id": "victory",    "name": "ויקטורי",        "regions": "tel_aviv,haifa"},
    {"id": "tiv_taam",   "name": "טיב טעם",        "regions": "tel_aviv,jerusalem"},
]

# (canonical, unit, base_price_per_unit)
PRODUCTS = [
    ("עגבניה",        "kg",   6.90),
    ("מלפפון",        "kg",   5.90),
    ("פלפל אדום",     "kg",  14.90),
    ("פלפל צהוב",     "kg",  15.90),
    ("פלפל ירוק",     "kg",   9.90),
    ("בצל",           "kg",   4.90),
    ("בצל סגול",      "kg",   7.90),
    ("שום",           "kg",  24.90),
    ("תפוח אדמה",     "kg",   4.50),
    ("בטטה",          "kg",   9.90),
    ("גזר",           "kg",   4.90),
    ("חסה",           "unit", 5.90),
    ("כרוב",          "unit", 7.90),
    ("ברוקולי",       "kg",  12.90),
    ("כרובית",        "kg",  10.90),
    ("קישוא",         "kg",   6.90),
    ("חציל",          "kg",   7.90),
    ("דלעת",          "kg",   5.90),
    ("לימון",         "kg",   8.90),
    ("פטרוזיליה",     "unit", 3.90),
]

# דמי משלוח וסף מינימום - חנות × אזור
DELIVERY = {
    # (store_id, region): (fee, min_order)
    ("rami_levy", "tel_aviv"):   (19.90, 199),
    ("rami_levy", "haifa"):      (24.90, 199),
    ("rami_levy", "jerusalem"):  (19.90, 199),
    ("shufersal", "tel_aviv"):   (29.90, 150),
    ("shufersal", "haifa"):      (29.90, 150),
    ("shufersal", "jerusalem"):  (29.90, 150),
    ("shufersal", "beer_sheva"): (34.90, 150),
    ("victory",   "tel_aviv"):   (14.90, 250),
    ("victory",   "haifa"):      (19.90, 250),
    ("tiv_taam",  "tel_aviv"):   (0.00,  300),  # free above 300
    ("tiv_taam",  "jerusalem"):  (25.00, 300),
}


def load_mock_data() -> None:
    with get_conn() as conn:
        for s in STORES:
            conn.execute(
                "INSERT INTO stores (id, name, regions) VALUES (?,?,?)",
                (s["id"], s["name"], s["regions"]),
            )

        product_ids = {}
        for canonical, unit, _ in PRODUCTS:
            cur = conn.execute(
                "INSERT INTO products (canonical, unit) VALUES (?,?)",
                (canonical, unit),
            )
            product_ids[canonical] = cur.lastrowid

        # לכל חנות: מחיר = בסיס * גורם חנות * רעש קל. חלק מהמוצרים לא זמינים.
        store_factors = {
            "rami_levy": 0.92,   # הכי זולה ממוצע
            "shufersal": 1.05,
            "victory":   0.98,
            "tiv_taam":  1.15,   # יקרה אבל מבצעים נקודתיים
        }
        for canonical, _unit, base in PRODUCTS:
            for s in STORES:
                # 10% סיכוי שהמוצר לא זמין בחנות
                if random.random() < 0.10:
                    continue
                factor = store_factors[s["id"]]
                # מבצע נקודתי - 20% הנחה בסיכוי 15%
                if random.random() < 0.15:
                    factor *= 0.80
                noise = random.uniform(0.95, 1.05)
                price = round(base * factor * noise, 2)
                conn.execute(
                    "INSERT INTO prices (store_id, product_id, price) VALUES (?,?,?)",
                    (s["id"], product_ids[canonical], price),
                )

        for (store_id, region), (fee, min_order) in DELIVERY.items():
            conn.execute(
                "INSERT INTO delivery_rules (store_id, region, fee, min_order) VALUES (?,?,?,?)",
                (store_id, region, fee, min_order),
            )

    print(f"נטען: {len(STORES)} חנויות, {len(PRODUCTS)} מוצרים, {len(DELIVERY)} כללי משלוח")
