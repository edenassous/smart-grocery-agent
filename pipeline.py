"""
Pipeline מלא: הורדת קבצים → פרסור → עדכון DB.

הרצה:
    python pipeline.py download   # רק הורדה
    python pipeline.py parse      # רק פרסור (אם כבר ירדו קבצים)
    python pipeline.py all        # שניהם
    python pipeline.py stats      # סטטיסטיקה על DB

שימוש מומלץ: python pipeline.py all
"""
import sys
import time
from pathlib import Path

from il_supermarket_scarper import ScarpingTask, ScraperFactory
from il_supermarket_scarper.utils import FileTypesFilters

# import הפרסר שכבר כתבנו
import parser as parser_module

# רשתות שאנחנו תומכים בהן
ENABLED_CHAINS = [
    ScraperFactory.RAMI_LEVY.name,
    ScraperFactory.SHUFERSAL.name,
    ScraperFactory.VICTORY.name,
]

# מספר קבצים מקסימלי לכל רשת. ככל שיותר - יותר כיסוי, יותר זמן.
FILES_PER_CHAIN = 10


def cmd_download() -> None:
    """מוריד עד FILES_PER_CHAIN קבצי PriceFull מכל רשת."""
    print(f"📥 מוריד עד {FILES_PER_CHAIN} קבצים מכל רשת ({len(ENABLED_CHAINS)} רשתות)")
    print(f"   זה עשוי לקחת 3-10 דקות, בהתאם לאינטרנט שלך.\n")

    start = time.time()
    scraper = ScarpingTask(
        enabled_scrapers=ENABLED_CHAINS,
        files_types=[FileTypesFilters.PRICE_FULL_FILE.name],
    )
    scraper.start(limit=FILES_PER_CHAIN)
    scraper.join()

    elapsed = time.time() - start
    print(f"\n✓ הורדה הסתיימה ב-{elapsed:.0f} שניות")

    # סיכום מהיר של מה ירד
    dumps = Path("dumps")
    if dumps.exists():
        for chain_dir in dumps.iterdir():
            if chain_dir.is_dir() and chain_dir.name != "status":
                files = [f for f in chain_dir.glob("*.xml") if "Price" in f.name]
                total_size_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
                print(f"   {chain_dir.name}: {len(files)} קבצים, {total_size_mb:.1f} MB")


def cmd_parse() -> None:
    """פרסר את כל הקבצים שב-dumps/ ועדכן את ה-DB."""
    print("📦 פורס קבצים ל-DB...\n")
    start = time.time()

    counts = parser_module.load_all_dumps()

    elapsed = time.time() - start
    total = sum(counts.values())
    print(f"\n✓ פרסור הסתיים ב-{elapsed:.0f} שניות. סה״כ {total:,} שורות מחיר.")


def cmd_stats() -> None:
    """מציג סטטיסטיקה מפורטת על ה-DB."""
    parser_module.show_stats()


def cmd_all() -> None:
    """הורדה + פרסור + סטטיסטיקה."""
    cmd_download()
    print()
    cmd_parse()
    print()
    cmd_stats()


COMMANDS = {
    "download": cmd_download,
    "parse":    cmd_parse,
    "stats":    cmd_stats,
    "all":      cmd_all,
}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd not in COMMANDS:
        print(f"שימוש: python pipeline.py {{{'|'.join(COMMANDS)}}}")
        sys.exit(1)
    COMMANDS[cmd]()
