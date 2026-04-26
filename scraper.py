"""
שלד ל-scraper של פורטלי שקיפות מחירים של רשתות המזון בישראל.

----------------------------------------------------------------------
חוק "להגברת האכיפה של דיני העבודה" ותקנות המחירים (קובץ פורמט PriceXXX)
מחייבים רשתות גדולות לפרסם קבצי XML עם כל המחירים כל יום.

לכל רשת פורטל משלה:
  - רמי לוי:     https://url.publishedprices.co.il  (user: RamiLevi, no pass)
  - שופרסל:     https://prices.shufersal.co.il
  - ויקטורי:     https://matrixcatalog.co.il
  - טיב טעם:    https://publishedprices.co.il (אותו פורטל של רמי לוי)
  ...

פורמט הקבצים (Price*.xml):
  <Root>
    <ChainId>...</ChainId>
    <StoreId>...</StoreId>
    <Items>
      <Item>
        <ItemCode>...</ItemCode>     # ברקוד
        <ItemName>...</ItemName>     # שם מוצר
        <ItemPrice>...</ItemPrice>
        <UnitOfMeasure>...</UnitOfMeasure>
        ...
      </Item>
    </Items>
  </Root>

הקבצים לרוב ב-gzip. יש גם PriceFull*.xml (מלא) ו-Price*.xml (עדכונים).

----------------------------------------------------------------------
המלצה חמה: אל תכתוב את זה מאפס.

ספריות קיימות שכבר פתרו את הפורטלים השונים:
  - https://github.com/erlichsefi/israeli-supermarket-scrapers
  - https://github.com/eladroz/superget

יש גם סטים ציבוריים של הקבצים כבר מפורסרים.
----------------------------------------------------------------------
"""
from typing import Iterator
from dataclasses import dataclass


@dataclass
class RawPriceItem:
    chain_id: str
    store_id: str  # החנות הפיזית, לא הרשת
    item_code: str
    item_name: str
    price: float
    unit_of_measure: str


def download_chain(chain: str) -> Iterator[RawPriceItem]:
    """
    TODO: להטמיע פר רשת.
    דוגמת flow:
      1. login/retrieve file list ב-portal של הרשת
      2. הורדת ה-PriceFull*.xml.gz הכי עדכני
      3. gunzip + parse XML
      4. yield RawPriceItem לכל פריט
    """
    raise NotImplementedError(
        f"חבר את {chain} - ראה ספריות קיימות בקומנטים למעלה"
    )


def normalize_to_canonical(raw: RawPriceItem) -> tuple[str, str] | None:
    """
    TODO: ממיר "עגבניה שרי אשכולות" → ("עגבניה", "kg").

    גישות:
      (1) מילון ידני של Top-100 מוצרים פופולריים. פשוט וטוב ל-80%.
      (2) embeddings (למשל text-embedding-3 של OpenAI או E5 multilingual)
          + cosine similarity מול רשימת "מוצרים קנוניים" שהגדרת.
      (3) LLM call לכל מוצר - יקר אבל הכי מדויק. עדיף לעשות batch פעם ביום.

    מחזיר None אם זה לא מוצר שמעניין אותנו (למשל לא ירק/פרי).
    """
    raise NotImplementedError
