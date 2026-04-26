"""
סקריפט חקר ראשוני - מוריד נתונים מ-3 רשתות.
"""
from il_supermarket_scarper import ScarpingTask, ScraperFactory
from il_supermarket_scarper.utils import FileTypesFilters

CHAINS = [
    ScraperFactory.RAMI_LEVY.name,
    ScraperFactory.SHUFERSAL.name,
    ScraperFactory.VICTORY.name,
]

scraper = ScarpingTask(
    enabled_scrapers=CHAINS,
    files_types=[
    FileTypesFilters.PRICE_FULL_FILE.name,
    FileTypesFilters.STORE_FILE.name,
],)

print(f"מוריד נתונים מ-{len(CHAINS)} רשתות: {', '.join(CHAINS)}")
print("מגבלה: עד 2 קבצים מכל רשת. זה עשוי לקחת 2-5 דקות...\n")

# limit=2 = עד 2 קבצים מכל רשת
scraper.start(limit=2)

# join() ממתין שה-thread יסיים לפני שהתוכנית יוצאת
scraper.join()

print("\n✓ הורדה הסתיימה")
